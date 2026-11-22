import { createClient } from "npm:@supabase/supabase-js@2";

const OWNER_ID = "ddfe2f5e-c5da-418c-b84c-60c8be6f7414";
const BUCKET = "gcf-source-media";
const PREFIX = `${OWNER_ID}/short-01/media`;
const REQUIRED = ["scene-01.mp4", "scene-02.mp4", "scene-03.mp4", "scene-04.mp4", "scene-05.mp4", "voiceover.wav"];
const URL_TTL_SECONDS = 600;

function constantTimeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

const secretKeys = JSON.parse(Deno.env.get("SUPABASE_SECRET_KEYS") ?? "{}");
const adminKey = secretKeys.default;
const supabaseUrl = Deno.env.get("SUPABASE_URL");
const gatewayToken = Deno.env.get("GCF_RENDER_GATEWAY_TOKEN");
if (!adminKey || !supabaseUrl || !gatewayToken) {
  throw new Error("Required server-side environment configuration is missing");
}
const supabaseAdmin = createClient(supabaseUrl, adminKey, {
  auth: { persistSession: false, autoRefreshToken: false },
});

Deno.serve(async (req) => {
  if (req.method !== "POST") return Response.json({ error: "Method not allowed" }, { status: 405 });
  const supplied = (req.headers.get("authorization") ?? "").replace(/^Bearer\s+/i, "");
  if (!constantTimeEqual(supplied, gatewayToken)) {
    return Response.json({ error: "Unauthorized" }, { status: 401, headers: { "Cache-Control": "no-store" } });
  }

  let body: { episode?: string };
  try { body = await req.json(); } catch { return Response.json({ error: "Invalid JSON body" }, { status: 400 }); }
  if (body.episode !== "short-01") return Response.json({ error: "Episode not allowed" }, { status: 400 });

  const files: Record<string, string> = {};
  const missing: string[] = [];
  for (const filename of REQUIRED) {
    const { data, error } = await supabaseAdmin.storage.from(BUCKET)
      .createSignedUrl(`${PREFIX}/${filename}`, URL_TTL_SECONDS, { download: filename });
    if (error || !data?.signedUrl) missing.push(filename);
    else files[filename] = data.signedUrl;
  }
  if (missing.length) return Response.json(
    { error: "Required source files are not all present", missing },
    { status: 409, headers: { "Cache-Control": "no-store" } },
  );
  return Response.json(
    { episode: "short-01", expires_in: URL_TTL_SECONDS, files },
    { headers: { "Cache-Control": "no-store, max-age=0" } },
  );
});
