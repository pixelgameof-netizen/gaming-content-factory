# Dynamic render pipeline: implementation contract

Status: engineering plan; not yet deployed. This document does not authorize a merge, production deployment, or publication.

## Current verified state

- Supabase has owner-scoped `content_packages`, `media_assets`, `rights_reviews`, `video_outputs`, `approvals`, and `publication_jobs`. The PR now stages (but does not apply) `supabase/migrations/202611220001_render_jobs.sql`, an owner-scoped render queue with constrained lifecycle states, package/output composite foreign keys, private owner-read RLS, and service-role-only writes. It includes `output_type` (`short`/`long_video`), destination platform (`youtube`, `youtube_shorts`, `tiktok`, `instagram_reels`, `facebook_reels`), aspect ratio, manifest, lifecycle, and eventual output reference.
- `gcf-ingest-gameplay` authenticates the caller, restricts upstream downloads to Wikimedia's upload host, and stores ingested files privately as rights candidates.
- `gcf-render-assets` is currently a legacy `short-01` implementation: fixed owner, fixed storage prefix, fixed filenames, and a gateway token. The live `rights_reviews.status` constraint allows `approved_by_owner` (not `approved`); `media_assets.rights_status` separately allows `approved`. Any dynamic rights gate must check both records and the publisher/game-policy, third-party-assets, and music booleans before creating a job.
- `gcf-upload-media` is also fixed to `short-01` and a fixed allowlist.
- The generic FFmpeg renderer consumes local episode folders. Its current GitHub workflow only reads files committed to the repository and uploads a short-lived Actions artifact; it does not fetch from Supabase or persist the final MP4 there.
- The latest renderer CI validates synthetic media and rights-gate rejection. It is not an end-to-end gameplay test.

## Target job contract

The UI/backend should create a render job for one authenticated owner and one content package. A job must have:
- an opaque job UUID;
- package UUID and owner UUID derived/verified server-side;
- requested aspect ratio (9:16 or 16:9);
- an immutable manifest of selected media asset IDs, their SHA-256 values, and roles;
- a script/voiceover asset reference and optional music/caption references;
- a status lifecycle such as queued -> preparing -> rendering -> uploading -> quality_check -> awaiting_owner, with failed/cancelled terminal states.

Never trust a client-supplied owner ID, storage path, rights status, hash, or package relationship. Resolve these from Supabase after authenticating the user.

## Rights gate

A source file being publicly reachable or carrying a Creative Commons/stock label is not sufficient by itself to authorize a gameplay edit. Before render:
1. Require the asset to be explicitly selected for this package.
2. Require an owner-approved rights review with evidence URL and scope.
3. Require separate confirmation of game/publisher policy, creator permission where relevant, third-party marks/releases, and music rights.
4. Reject revoked, expired, blocked, or candidate-only assets.
5. Record the exact asset hash and review IDs in the render manifest.

Do not use YouTube/TikTok scraping or download paths that bypass platform controls. Use those platforms for permitted discovery/reference, and ingest only from a source with an authorized download/reuse route.

## Secure runner hand-off

Do not pass Supabase service-role keys, GitHub tokens, permanent gateway secrets, or signed Storage URLs as workflow_dispatch inputs. Workflow inputs are visible in run metadata and may be echoed in logs.

Preferred hand-off:
1. The authenticated backend creates a short-lived render job and stores a hash of a one-time random ticket, bound to the job, owner, and expiry.
2. The backend dispatches the fixed workflow using only a non-secret job identifier.
3. The runner authenticates using a server-managed GitHub Actions secret or a verifiable short-lived workload identity, then exchanges the ticket through a server endpoint. The ticket itself must not be placed in public workflow inputs or logs.
4. The endpoint returns only short-lived signed URLs for the exact approved asset IDs in the immutable manifest. Use no-store responses and short expiry.
5. Runner downloads to ephemeral workspace, verifies SHA-256 against the manifest, renders, computes final SHA-256, and uploads the result through a narrowly scoped, expiring upload grant.
6. Server validates job ownership/state and output metadata, then inserts `video_outputs` and advances the job state.

If the secure credential exchange cannot be completed, stop the job rather than falling back to public URLs or embedding secrets in the workflow.

## Output and approval contract

- Store final MP4 in private `gcf-video-outputs`.
- Record bucket, object path, output type, platform, aspect ratio, duration, version, quality status, and SHA-256 in `video_outputs`.
- Create an approval record bound to both output ID and exact output version/hash.
- Any regenerated or modified file gets a new hash/version and invalidates previous approval.
- Publication worker must verify a current approval for the exact hash and exact platform immediately before publishing.
- No automatic publication or scheduling until the owner explicitly approves the exact output/hash/platform.

## Required end-to-end acceptance tests

1. Unauthenticated request is rejected.
2. User A cannot create or fetch User B's package/assets/job/output.
3. Candidate, missing, expired, revoked, or blocked rights review prevents rendering.
4. A changed source file fails manifest hash verification.
5. Arbitrary episode names, storage paths, hosts, and filenames are rejected.
6. Workflow logs and run metadata contain no bearer tokens, signed URLs, or service-role keys.
7. Successful render uploads an MP4 to private Storage and registers matching SHA-256 metadata.
8. Approval is bound to the exact output version/hash; a changed hash cannot publish.
9. A failed upload or DB insert cleans up temporary objects and leaves a recoverable failed job.
10. Test with a real, authorized gameplay clip and final voiceover; synthetic CI media is not sufficient.

## Remaining implementation sequence

1. Apply and review the staged `render_jobs` migration, then build dynamic job creation/status endpoints and owner-scoped manifest validation. The table is not deployed yet.
2. Replace the fixed `short-01` fetch/upload functions with job-scoped, expiring hand-off endpoints.
3. Update the generic workflow to fetch, verify, render, and upload dynamically.
4. Wire the Floot UI to create jobs, show progress, preview private outputs, and collect hash-bound approval.
5. Run end-to-end tests with authorized gameplay.
6. Review security findings and deployment settings; keep the existing draft PR unmerged until explicitly approved.


## Dynamic asset handoff implementation (staged, not deployed)

A new Edge Function source file is staged at `supabase/functions/gcf-render-job-assets/index.ts`.
It is intentionally separate from the live legacy `gcf-render-assets` function, so no production behavior is replaced.

### Request and response contract

- Method: POST; authorization: a GitHub Actions OIDC identity token with audience `gcf-render-job-assets`. The function verifies the issuer/signature and restricts repository ID, owner actor ID, workflow file, and allowed branch refs; no shared bearer secret is needed.
- Request body: `{ "job_id": "<render_jobs UUID>" }`. The response also carries the job's output type, destination platform, and aspect ratio.
- The function reads the job from `render_jobs`, then resolves only assets whose owner and package match that job.
- Manifest entries use `{ "asset_id": "<media_assets UUID>", "file_name": "scene-01.mp4" }`.
- Accepted source roles: `gameplay`, `trailer`, exactly one `voiceover`, and optional `music`.
- Gameplay/trailer assets must be approved MP4s; voiceover and music must be WAV files.
- Every source-backed gameplay/trailer/music asset (and any source-backed voiceover) must have `media_assets.rights_status='approved'` and the latest matching `rights_reviews` row must be `approved_by_owner`, with commercial use, derivatives, redistribution, game-policy and third-party checks, owner review evidence, and a non-expired license. Music additionally requires `music_rights_verified=true`.
- Only private `gcf-source-media` objects beneath the job owner's storage prefix are signed. Every asset must carry a valid SHA-256. URLs expire after 10 minutes. Responses are no-store. The function does not choose among historical rights reviews arbitrarily: it evaluates the most recent review per source. It returns the rights evidence required by the FFmpeg renderer.
- The function does not publish, mutate approval state, or mark a render job complete. `.github/workflows/render-job.yml` now stages a manual OIDC-protected workflow that fetches the signed assets, verifies SHA-256, builds the renderer rights manifest, and produces a one-day review artifact. It does not yet upload the final MP4 to Supabase.

### Deployment gate

This source depends on the staged `render_jobs` migration. It must be type-checked in CI, reviewed, and deployed only after the migration is applied and a controlled authenticated test succeeds. The function is not deployed to Supabase yet. The new CI step runs `deno check` against this source.
