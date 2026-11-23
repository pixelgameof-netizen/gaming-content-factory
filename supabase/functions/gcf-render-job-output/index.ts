import { createClient } from "npm:@supabase/supabase-js@2";
import { createRemoteJWKSet, jwtVerify } from "npm:jose@5.9.6";

const BUCKET = "gcf-video-outputs";
const MAX_OUTPUT_BYTES = 50 * 1024 * 1024;
const GITHUB_JWKS = createRemoteJWKSet(new URL("https://token.actions.githubusercontent.com/.well-known/jwks"));
const ALLOWED_REFS = new Set(["refs/heads/hardening/renderer-rights-validation", "refs/heads/main"]);
const REPOSITORY = "pixelgameof-netizen/gaming-content-factory";
const WORKFLOW_PATH = `${REPOSITORY}/.github/workflows/render-job.yml`;
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const HASH_RE = /^[a-f0-9]{64}$/i;

function json(body: unknown, status = 200): Response {
  return Response.json(body, {
    status,
    headers: { "Cache-Control": "no-store, max-age=0", Pragma: "no-cache" },
  });
}

const secretKeys = JSON.parse(Deno.env.get("SUPABASE_SECRET_KEYS") ?? "{}");
const adminKey = secretKeys.default;
const supabaseUrl = Deno.env.get("SUPABASE_URL");
if (!adminKey || !supabaseUrl) {
  throw new Error("Required server-side environment configuration is missing");
}
const admin = createClient(supabaseUrl, adminKey, {
  auth: { persistSession: false, autoRefreshToken: false },
});

async function verifyWorkflow(req: Request): Promise<boolean> {
  const supplied = (req.headers.get("authorization") ?? "").replace(/^Bearer\s+/i, "");
  if (!supplied) return false;
  try {
    const { payload } = await jwtVerify(supplied, GITHUB_JWKS, {
      issuer: "https://token.actions.githubusercontent.com",
      audience: "gcf-render-job-output",
    });
    const expectedWorkflow = typeof payload.ref === "string" ? `${WORKFLOW_PATH}@${payload.ref}` : "";
    return payload.repository === REPOSITORY &&
      String(payload.repository_id) === "1465927071" &&
      String(payload.actor_id) === "359316091" &&
      typeof payload.ref === "string" &&
      ALLOWED_REFS.has(payload.ref) &&
      payload.workflow_ref === expectedWorkflow;
  } catch {
    return false;
  }
}

function validQc(qc: Record<string, unknown>, aspect: string): boolean {
  const dimensions = aspect === "9:16" ? [1080, 1920] : [1920, 1080];
  return qc.status === "passed" &&
    typeof qc.sha256 === "string" && HASH_RE.test(qc.sha256) &&
    Number.isInteger(qc.size_bytes) && Number(qc.size_bytes) > 1024 &&
    Number(qc.size_bytes) <= MAX_OUTPUT_BYTES &&
    typeof qc.duration_seconds === "number" && Number.isFinite(qc.duration_seconds) &&
    qc.duration_seconds > 1 && qc.duration_seconds <= 900 &&
    qc.aspect_ratio === aspect &&
    qc.width === dimensions[0] && qc.height === dimensions[1] &&
    qc.video_codec === "h264" && qc.audio_codec === "aac" &&
    typeof qc.frame_rate === "number" && qc.frame_rate >= 23 && qc.frame_rate <= 60;
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return json({ error: "Method not allowed" }, 405);
  if (!await verifyWorkflow(req)) return json({ error: "GitHub Actions workflow identity is not authorized" }, 401);

  let body: {
    action?: unknown;
    job_id?: unknown;
    storage_path?: unknown;
    qc_report?: unknown;
  };
  try {
    body = await req.json();
  } catch {
    return json({ error: "Invalid JSON body" }, 400);
  }
  if (typeof body.job_id !== "string" || !UUID_RE.test(body.job_id)) {
    return json({ error: "A valid job_id is required" }, 400);
  }

  if (body.action === "prepare_upload") {
    const { data, error } = await admin.rpc("gcf_prepare_render_job_upload", {
      p_job_id: body.job_id,
    });
    if (error) return json({ error: "Render job is not available for upload" }, 409);
    const job = Array.isArray(data) ? data[0] : data;
    if (!job?.id || !job.owner_id || !job.package_id) {
      return json({ error: "Render job could not be prepared" }, 409);
    }

    const storagePath = `${job.owner_id}/${job.package_id}/render-jobs/${job.id}/${crypto.randomUUID()}.mp4`;
    const { data: signed, error: signError } = await admin.storage
      .from(BUCKET)
      .createSignedUploadUrl(storagePath, { upsert: false });
    if (signError || !signed?.signedUrl || !signed?.token) {
      return json({ error: "Could not create a one-time output upload URL" }, 502);
    }
    return json({
      job_id: job.id,
      bucket: BUCKET,
      storage_path: storagePath,
      upload_token: signed.token,
      expires_in: 7200,
      max_bytes: MAX_OUTPUT_BYTES,
    });
  }

  if (body.action !== "finalize") {
    return json({ error: "Unsupported action" }, 400);
  }
  if (typeof body.storage_path !== "string" || typeof body.qc_report !== "object" || body.qc_report === null) {
    return json({ error: "storage_path and qc_report are required" }, 400);
  }

  const { data: jobRows, error: jobError } = await admin.rpc("gcf_get_render_job_for_worker", {
    p_job_id: body.job_id,
  });
  if (jobError) return json({ error: "Unable to load render job" }, 500);
  const job = Array.isArray(jobRows) ? jobRows[0] : jobRows;
  if (!job) return json({ error: "Render job not found" }, 404);
  if (job.status !== "uploading" && job.status !== "awaiting_owner") {
    return json({ error: "Render job is not awaiting output finalization" }, 409);
  }
  if (job.expires_at && Date.parse(job.expires_at) <= Date.now() && job.status !== "awaiting_owner") {
    return json({ error: "Render job expired" }, 410);
  }

  const expectedPrefix = `${job.owner_id}/${job.package_id}/render-jobs/${job.id}/`;
  const fileName = body.storage_path.slice(expectedPrefix.length);
  if (!body.storage_path.startsWith(expectedPrefix) || !/^[0-9a-f-]{36}\.mp4$/i.test(fileName)) {
    return json({ error: "Output storage path is outside this render job" }, 403);
  }

  const qc = body.qc_report as Record<string, unknown>;
  if (!validQc(qc, job.aspect_ratio)) {
    return json({ error: "QC report does not satisfy the render output contract" }, 422);
  }

  const { data: object, error: downloadError } = await admin.storage.from(BUCKET).download(body.storage_path);
  if (downloadError || !object) return json({ error: "Rendered MP4 is not present in private Storage" }, 404);
  const bytes = new Uint8Array(await object.arrayBuffer());
  if (bytes.byteLength !== Number(qc.size_bytes) || bytes.byteLength > MAX_OUTPUT_BYTES) {
    if (job.status === "uploading") await admin.storage.from(BUCKET).remove([body.storage_path]);
    return json({ error: "Stored output size does not match the QC report or exceeds the bucket limit" }, 422);
  }
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  const actualHash = Array.from(new Uint8Array(digest)).map((value) => value.toString(16).padStart(2, "0")).join("");
  if (actualHash !== String(qc.sha256).toLowerCase()) {
    if (job.status === "uploading") await admin.storage.from(BUCKET).remove([body.storage_path]);
    return json({ error: "Stored MP4 SHA-256 does not match the QC report" }, 422);
  }

  const { data: finalized, error: finalizeError } = await admin.rpc("gcf_finalize_render_job_output", {
    p_job_id: job.id,
    p_owner_id: job.owner_id,
    p_storage_path: body.storage_path,
    p_sha256: actualHash,
    p_duration_seconds: qc.duration_seconds,
  });
  if (finalizeError) return json({ error: "Output verification succeeded, but atomic registration failed" }, 500);
  const result = Array.isArray(finalized) ? finalized[0] : finalized;
  return json({
    status: "awaiting_owner",
    job_id: job.id,
    output_id: result?.output_id,
    approval_id: result?.approval_id,
    version_no: result?.version_no,
    sha256: result?.output_sha256 ?? actualHash,
    platform: job.platform,
    aspect_ratio: job.aspect_ratio,
    publication: "not_published",
  });
});
