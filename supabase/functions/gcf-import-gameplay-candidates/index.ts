import { createClient } from "npm:@supabase/supabase-js@2";
import { createRemoteJWKSet, jwtVerify } from "npm:jose@5.9.6";

const REPOSITORY = "pixelgameof-netizen/gaming-content-factory";
const REPOSITORY_ID = "1465927071";
const ACTOR_ID = "359316091";
const OWNER_ID = "ddfe2f5e-c5da-418c-b84c-60c8be6f7414";
const PROJECT_ID = "2c8a09d4-f89a-47c5-a1fd-28704db20211";
const WORKFLOW_PATH = `${REPOSITORY}/.github/workflows/gameplay-hunter.yml`;
const WORKFLOW_REF = `${WORKFLOW_PATH}@refs/heads/main`;
const JWKS = createRemoteJWKSet(new URL("https://token.actions.githubusercontent.com/.well-known/jwks"));
const MAX_CANDIDATES = 48;
const LICENSES: Record<string, { version: string; url: string }> = {
  "CC0": { version: "1.0", url: "https://creativecommons.org/publicdomain/zero/1.0/" },
  "CC BY 3.0": { version: "3.0", url: "https://creativecommons.org/licenses/by/3.0/" },
  "CC BY 4.0": { version: "4.0", url: "https://creativecommons.org/licenses/by/4.0/" },
};

function json(body: unknown, status = 200): Response {
  return Response.json(body, {
    status,
    headers: { "Cache-Control": "no-store, max-age=0", Pragma: "no-cache" },
  });
}

function safeText(value: unknown, max: number): string {
  if (typeof value !== "string") return "";
  return value.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim().slice(0, max);
}

function trustedUrl(value: unknown, host: string): URL | null {
  if (typeof value !== "string" || value.length > 2048) return null;
  try {
    const parsed = new URL(value);
    if (parsed.protocol !== "https:" || parsed.hostname !== host ||
        parsed.username || parsed.password) return null;
    return parsed;
  } catch {
    return null;
  }
}

function validLicenseUrl(value: unknown, license: string): boolean {
  const expected = LICENSES[license];
  if (!expected) return false;
  const parsed = trustedUrl(value, "creativecommons.org") ??
    trustedUrl(value, "www.creativecommons.org");
  return Boolean(parsed && parsed.pathname.replace(/\/$/, "") === expected.url.replace("https://creativecommons.org", "").replace(/\/$/, ""));
}

const secretKeys = JSON.parse(Deno.env.get("SUPABASE_SECRET_KEYS") ?? "{}");
const adminKey = secretKeys.default;
const supabaseUrl = Deno.env.get("SUPABASE_URL");
if (!adminKey || !supabaseUrl) throw new Error("Missing server-side Supabase configuration");
const admin = createClient(supabaseUrl, adminKey, {
  auth: { persistSession: false, autoRefreshToken: false },
});

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return json({ error: "Method not allowed" }, 405);
  const supplied = (req.headers.get("authorization") ?? "").replace(/^Bearer\s+/i, "");
  if (!supplied) return json({ error: "Missing GitHub Actions identity token" }, 401);

  let identity;
  try {
    const verified = await jwtVerify(supplied, JWKS, {
      issuer: "https://token.actions.githubusercontent.com",
      audience: "gcf-import-gameplay-candidates",
    });
    identity = verified.payload;
  } catch {
    return json({ error: "Invalid GitHub Actions identity token" }, 401);
  }

  if (identity.repository !== REPOSITORY ||
      String(identity.repository_id) !== REPOSITORY_ID ||
      String(identity.actor_id) !== ACTOR_ID ||
      identity.ref !== "refs/heads/main" ||
      identity.workflow_ref !== WORKFLOW_REF ||
      !["schedule", "workflow_dispatch"].includes(String(identity.event_name))) {
    return json({ error: "GitHub Actions workflow identity is not authorized" }, 403);
  }

  let body: { candidates?: unknown };
  try { body = await req.json(); } catch { return json({ error: "Invalid JSON body" }, 400); }
  if (!Array.isArray(body.candidates) || body.candidates.length > MAX_CANDIDATES) {
    return json({ error: `Provide an array of no more than ${MAX_CANDIDATES} candidates` }, 400);
  }

  let imported = 0;
  let alreadyPresent = 0;
  let rejected = 0;
  const errors: string[] = [];

  for (const raw of body.candidates) {
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
      rejected++;
      continue;
    }
    const item = raw as Record<string, unknown>;
    const license = typeof item.license === "string" ? item.license : "";
    const licenseInfo = LICENSES[license];
    const sourcePage = trustedUrl(item.source_page, "commons.wikimedia.org");
    const mediaUrl = trustedUrl(item.direct_media_url, "upload.wikimedia.org");
    const title = safeText(item.title, 300);
    const game = safeText(item.game_query, 100);
    const mime = typeof item.mime === "string" ? item.mime.toLowerCase() : "";

    if (!licenseInfo || !sourcePage || !sourcePage.pathname.startsWith("/wiki/File:") ||
        !mediaUrl || !title || !game || !mime.startsWith("video/") ||
        item.rights_status !== "candidate" || item.downloaded !== false ||
        item.auto_approved !== false || !validLicenseUrl(item.license_url, license)) {
      rejected++;
      continue;
    }

    const { data: existing, error: existingError } = await admin.from("sources")
      .select("id")
      .eq("owner_id", OWNER_ID)
      .eq("source_url", sourcePage.toString())
      .maybeSingle();
    if (existingError) {
      errors.push(`Lookup failed for ${title}: ${existingError.message}`);
      continue;
    }
    if (existing?.id) {
      alreadyPresent++;
      continue;
    }

    const metadata = {
      title,
      game_query: game,
      source_page: sourcePage.toString(),
      direct_media_url: mediaUrl.toString(),
      mime,
      license,
      license_url: licenseInfo.url,
      artist: safeText(item.artist, 1000),
      credit: safeText(item.credit, 1000),
      usage_terms: safeText(item.usage_terms, 1000),
      description: safeText(item.description, 1800),
      attribution_required: license !== "CC0",
      publisher_gameplay_policy_review_required: true,
      music_rights_review_required: true,
      rights_status: "candidate",
    };

    const { data: source, error: sourceError } = await admin.from("sources").insert({
      owner_id: OWNER_ID,
      project_id: PROJECT_ID,
      platform: "wikimedia_commons",
      title,
      source_url: sourcePage.toString(),
      creator_name: metadata.artist || null,
      game_title: game,
      source_type: "video",
      discovery_method: "github_gameplay_hunter",
      notes: JSON.stringify(metadata),
    }).select("id").single();

    if (sourceError || !source?.id) {
      errors.push(`Source insert failed for ${title}: ${sourceError?.message ?? "missing source id"}`);
      continue;
    }

    const { error: rightsError } = await admin.from("rights_reviews").insert({
      owner_id: OWNER_ID,
      source_id: source.id,
      status: "candidate",
      license_name: license,
      license_version: licenseInfo.version,
      license_url: licenseInfo.url,
      commercial_use: true,
      derivatives_allowed: true,
      redistribution_allowed: true,
      attribution_required: license !== "CC0",
      music_rights_verified: false,
      game_policy_verified: false,
      third_party_assets_verified: false,
      evidence_summary: "License metadata discovered on Wikimedia Commons. This record is candidate-only. The underlying game/publisher policy, soundtrack, third-party assets and final attribution remain unverified. No owner approval has been recorded.",
    });

    if (rightsError) {
      await admin.from("sources").delete().eq("id", source.id).eq("owner_id", OWNER_ID);
      errors.push(`Rights evidence insert failed for ${title}: ${rightsError.message}`);
      continue;
    }
    imported++;
  }

  return json({
    imported,
    already_present: alreadyPresent,
    rejected,
    errors: errors.slice(0, 10),
    rights_status: "candidate_only",
    media_downloaded: false,
    render_jobs_created: false,
    auto_approval: false,
    publishing: false,
  });
});
