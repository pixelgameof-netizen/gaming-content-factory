import { withSupabase } from "npm:@supabase/server";

const OWNER_ID = "ddfe2f5e-c5da-418c-b84c-60c8be6f7414";
const BUCKET = "gcf-source-media";
const PREFIX = `${OWNER_ID}/short-01/media`;
const REQUIRED = ["scene-01.mp4", "scene-02.mp4", "scene-03.mp4", "scene-04.mp4", "scene-05.mp4", "voiceover.wav"];
const URL_TTL_SECONDS = 600;

Deno.serve(withSupabase({ auth: "secret:gcf-render" }, async (req, ctx) => {
  if (req.method !== "POST") return Response.json({ error: "Method not allowed" }, { status: 405 });
  let body: { episode?: string };
  try { body = await req.json(); } catch { return Response.json({ error: "Invalid JSON body" }, { status: 400 }); }
  if (body.episode !== "short-01") return Response.json({ error: "Episode not allowed" }, { status: 400 });

  const files: Record<string, string> = {};
  const missing: string[] = [];
  for (const filename of REQUIRED) {
    const { data, error } = await ctx.supabaseAdmin.storage.from(BUCKET)
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
}));
