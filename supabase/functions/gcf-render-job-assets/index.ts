import { createClient } from "npm:@supabase/supabase-js@2";
import { createRemoteJWKSet, jwtVerify } from "npm:jose@5.9.6";

const BUCKET = "gcf-source-media";
const URL_TTL_SECONDS = 600;
const GITHUB_JWKS = createRemoteJWKSet(new URL("https://token.actions.githubusercontent.com/.well-known/jwks"));
const ALLOWED_REFS = new Set(["refs/heads/hardening/renderer-rights-validation", "refs/heads/main"]);
const REPOSITORY = "pixelgameof-netizen/gaming-content-factory";
const WORKFLOW_PATH = `${REPOSITORY}/.github/workflows/render-job.yml`;
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

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

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return json({ error: "Method not allowed" }, 405);
  const supplied = (req.headers.get("authorization") ?? "").replace(/^Bearer\s+/i, "");
  if (!supplied) return json({ error: "Missing GitHub Actions identity token" }, 401);
  let identity;
  try {
    const verified = await jwtVerify(supplied, GITHUB_JWKS, {
      issuer: "https://token.actions.githubusercontent.com",
      audience: "gcf-render-job-assets",
    });
    identity = verified.payload;
  } catch {
    return json({ error: "Invalid GitHub Actions identity token" }, 401);
  }
  const expectedWorkflow = typeof identity.ref === "string" ? `${WORKFLOW_PATH}@${identity.ref}` : "";
  if (identity.repository !== REPOSITORY || String(identity.repository_id) !== "1465927071" ||
      String(identity.actor_id) !== "359316091" || typeof identity.ref !== "string" ||
      !ALLOWED_REFS.has(identity.ref) || identity.workflow_ref !== expectedWorkflow) {
    return json({ error: "GitHub Actions workflow identity is not authorized" }, 403);
  }

  let body: { job_id?: unknown };
  try { body = await req.json(); } catch { return json({ error: "Invalid JSON body" }, 400); }
  if (typeof body.job_id !== "string" || !UUID_RE.test(body.job_id)) {
    return json({ error: "A valid job_id is required" }, 400);
  }

  const { data: jobRows, error: jobError } = await admin.rpc("gcf_get_render_job_for_worker", {
    p_job_id: body.job_id,
  });
  if (jobError) return json({ error: "Unable to load render job" }, 500);
  const job = Array.isArray(jobRows) ? jobRows[0] : jobRows;
  if (!job) return json({ error: "Render job not found" }, 404);
  if (job.status !== "queued" && job.status !== "preparing" && job.status !== "uploading") {
    return json({ error: "Render job is not available for asset handoff", status: job.status }, 409);
  }
  if (job.expires_at && Date.parse(job.expires_at) <= Date.now()) {
    return json({ error: "Render job expired" }, 410);
  }
  if (!["9:16", "16:9"].includes(job.aspect_ratio)) {
    return json({ error: "Unsupported output aspect ratio" }, 422);
  }

  const manifest = job.manifest as { assets?: unknown };
  if (!manifest || !Array.isArray(manifest.assets) || manifest.assets.length < 2 || manifest.assets.length > 20) {
    return json({ error: "Manifest must contain between 2 and 20 assets" }, 422);
  }
  const requested = manifest.assets as Array<{ asset_id?: unknown; file_name?: unknown }>;
  const seenNames = new Set<string>();
  const ids: string[] = [];
  for (const item of requested) {
    if (!item || typeof item.asset_id !== "string" || !UUID_RE.test(item.asset_id) ||
        typeof item.file_name !== "string" || item.file_name.includes("/") || item.file_name.includes("\\") ||
        item.file_name === "." || item.file_name === ".." || !/^[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}$/.test(item.file_name)) {
      return json({ error: "Invalid asset manifest entry" }, 422);
    }
    if (seenNames.has(item.file_name)) return json({ error: "Duplicate file name in manifest" }, 422);
    seenNames.add(item.file_name);
    ids.push(item.asset_id);
  }

  const { data: assets, error: assetsError } = await admin
    .from("media_assets")
    .select("id,owner_id,package_id,source_id,asset_role,storage_bucket,storage_path,mime_type,sha256,rights_status")
    .in("id", ids)
    .eq("owner_id", job.owner_id)
    .eq("package_id", job.package_id)
    .eq("rights_status", "approved");
  if (assetsError) return json({ error: "Unable to load render assets" }, 500);
  if (!assets || assets.length !== ids.length) {
    return json({ error: "One or more assets are missing, unapproved, or outside this package" }, 403);
  }

  const byId = new Map(assets.map((asset) => [asset.id, asset]));
  const sourceIds = [...new Set(assets.map((asset) => asset.source_id).filter(Boolean))] as string[];
  const { data: reviews, error: reviewsError } = sourceIds.length
    ? await admin.from("rights_reviews")
      .select("source_id,status,commercial_use,derivatives_allowed,redistribution_allowed,music_rights_verified,game_policy_verified,third_party_assets_verified,license_url,expires_at,reviewed_by,reviewed_at,created_at")
      .eq("owner_id", job.owner_id)
      .in("source_id", sourceIds)
      .order("created_at", { ascending: false })
    : { data: [], error: null };
  if (reviewsError) return json({ error: "Unable to load rights reviews" }, 500);
  const reviewBySource = new Map();
  for (const review of reviews ?? []) {
    if (!reviewBySource.has(review.source_id)) reviewBySource.set(review.source_id, review);
  }
  const { data: sources, error: sourcesError } = sourceIds.length
    ? await admin.from("sources").select("id,source_url").eq("owner_id", job.owner_id).in("id", sourceIds)
    : { data: [], error: null };
  if (sourcesError) return json({ error: "Unable to load source evidence" }, 500);
  const sourceById = new Map((sources ?? []).map((source) => [source.id, source]));

  let sceneCount = 0;
  let voiceCount = 0;
  const files: Array<{ file_name: string; role: string; url: string; sha256: string | null; rights: Record<string, unknown> }> = [];
  for (const item of requested) {
    const asset = byId.get(item.asset_id as string)!;
    const fileName = item.file_name as string;
    const role = asset.asset_role as string;

    if (role === "gameplay" || role === "trailer") {
      if (!/^scene-\d{2,3}\.mp4$/.test(fileName) || asset.mime_type !== "video/mp4") {
        return json({ error: "Gameplay/trailer assets must be named scene-NN.mp4 and use video/mp4" }, 422);
      }
      sceneCount++;
    } else if (role === "voiceover") {
      if (fileName !== "voiceover.wav" || !["audio/wav", "audio/x-wav"].includes(asset.mime_type ?? "")) {
        return json({ error: "Voiceover must be voiceover.wav with WAV audio MIME type" }, 422);
      }
      voiceCount++;
    } else if (role === "music") {
      if (fileName !== "music.wav" || !["audio/wav", "audio/x-wav"].includes(asset.mime_type ?? "")) {
        return json({ error: "Music must be music.wav with WAV audio MIME type" }, 422);
      }
    } else {
      return json({ error: `Unsupported render asset role: ${role}` }, 422);
    }

    if (typeof asset.sha256 !== "string" || !/^[a-f0-9]{64}$/i.test(asset.sha256)) {
      return json({ error: `Asset is missing a valid SHA-256: ${asset.id}` }, 422);
    }

    if (asset.storage_bucket !== BUCKET || typeof asset.storage_path !== "string" ||
        !asset.storage_path.startsWith(`${job.owner_id}/`) ||
        asset.storage_path.split("/").some((part: string) => part === ".." || part === ".")) {
      return json({ error: "Asset storage location is invalid" }, 403);
    }

    if ((role === "gameplay" || role === "trailer" || role === "music") && !asset.source_id) {
      return json({ error: "Source-backed media requires a rights review" }, 403);
    }
    if (asset.source_id) {
      const review = reviewBySource.get(asset.source_id);
      const commonApproved = review?.status === "approved_by_owner" &&
        review.commercial_use === true && review.derivatives_allowed === true &&
        review.redistribution_allowed === true && review.game_policy_verified === true &&
        review.third_party_assets_verified === true && review.music_rights_verified === true && Boolean(review.license_url) &&
        review.reviewed_by === job.owner_id && Boolean(review.reviewed_at) &&
        (!review.expires_at || Date.parse(review.expires_at) > Date.now());
      if (!commonApproved || (role === "music" && review?.music_rights_verified !== true)) {
        return json({ error: `Rights review incomplete for asset ${asset.id}` }, 403);
      }
    }

    const review = asset.source_id ? reviewBySource.get(asset.source_id) : null;
    const source = asset.source_id ? sourceById.get(asset.source_id) : null;
    const reviewerApproved = !asset.source_id || (review?.reviewed_by === job.owner_id && Boolean(review?.reviewed_at));
    const rights: Record<string, unknown> = role === "voiceover" && !asset.source_id
      ? { status: "approved", rights_confirmed: true, reviewer_approved: true }
      : {
        status: "approved",
        commercial_use_confirmed: review?.commercial_use === true,
        publisher_policy_verified: review?.game_policy_verified === true,
        third_party_assets_verified: review?.third_party_assets_verified === true,
        music_rights_verified: review?.music_rights_verified === true,
        rights_confirmed: true,
        reviewer_approved: reviewerApproved,
        source_url: source?.source_url ?? "",
        license_url: review?.license_url ?? "",
      };
    const { data: signed, error: signError } = await admin.storage.from(BUCKET)
      .createSignedUrl(asset.storage_path, URL_TTL_SECONDS, { download: fileName });
    if (signError || !signed?.signedUrl) return json({ error: "Unable to sign a source asset" }, 502);
    files.push({ file_name: fileName, role, url: signed.signedUrl, sha256: asset.sha256 ?? null, rights });
  }

  if (sceneCount < 1 || voiceCount !== 1) {
    return json({ error: "A render requires at least one approved gameplay scene and exactly one approved voiceover" }, 422);
  }
  return json({
    job_id: job.id,
    package_id: job.package_id,
    output_type: job.output_type,
    platform: job.platform,
    aspect_ratio: job.aspect_ratio,
    expires_in: URL_TTL_SECONDS,
    files,
  });
});
