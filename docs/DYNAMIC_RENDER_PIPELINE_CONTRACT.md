# Dynamic render pipeline: implementation contract

Status: engineering plan; not yet deployed. This document does not authorize a merge, production deployment, or publication.

## Current verified state

- Supabase has owner-scoped `content_packages`, `media_assets`, `rights_reviews`, `video_outputs`, `approvals`, and `publication_jobs`. The PR stages (but does not apply) `supabase/migrations/202611220001_render_jobs.sql`, an owner-scoped render queue with constrained lifecycle states, package/output composite foreign keys, private owner-read RLS, and service-role-only writes. It includes `output_type` (`short`/`long_video`), destination platform (`youtube`, `youtube_shorts`, `tiktok`, `instagram_reels`, `facebook_reels`), aspect ratio, manifest, lifecycle, and eventual output reference.
- `gcf-ingest-gameplay` authenticates the caller, restricts upstream downloads to Wikimedia's upload host, and stores ingested files privately as rights candidates.
- `gcf-render-assets` is currently a legacy `short-01` implementation: fixed owner, fixed storage prefix, fixed filenames, and a gateway token. The live `rights_reviews.status` constraint allows `approved_by_owner` (not `approved`); `media_assets.rights_status` separately allows `approved`. Any dynamic rights gate must check both records and the publisher/game-policy, third-party-assets, and music booleans before creating a job.
- `gcf-upload-media` is also fixed to `short-01` and a fixed allowlist.
- The generic FFmpeg renderer consumes local episode folders. Its dynamic GitHub workflow fetches approved private assets using short-lived URLs, verifies their SHA-256 values, renders, runs media QC, uploads the MP4 to private Supabase Storage using a signed resumable TUS token, and asks a server-side finalizer to verify the stored bytes and register the output. A one-day GitHub review artifact remains as a temporary secondary copy.
- `render/quality_check.py` now validates MP4 container readability, required H.264 video and AAC audio streams, target dimensions, 23–60 fps, duration (over 1 and at most 900 seconds), audio/video duration agreement, and a streaming SHA-256 digest. It writes a machine-readable QC report. The GitHub CI runs `45266441850` and `45267064405` passed on earlier intermediate revisions, including Deno type-checking, a positive synthetic render, and rejection of a silent MP4. The latest migration, TUS uploader, and unit-test edits have not yet been exercised by a fresh GitHub Actions run.
- The output bucket is private and currently capped at 50 MiB; the QC gate enforces that cap. Long-form output above this size is blocked until a storage-limit change is reviewed.
- Worker queue access uses restricted service-role-only RPCs, so the new queue table does not need to be exposed to the public Data API for worker handoff. Authenticated app-side job creation/status UI is still pending.
- CI media is synthetic; it is not an end-to-end gameplay test.

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
5. Runner downloads to ephemeral workspace, verifies SHA-256 against the manifest, renders, runs the QC gate, and computes the final SHA-256.
6. A worker-only endpoint creates a one-time signed upload token bound to a unique object path under the job owner/package prefix. The runner uses the token for a resumable TUS upload; the token and URL never enter workflow inputs or artifacts.
7. The finalizer downloads the stored object, checks its byte count and SHA-256 against the QC report, then calls a transaction-safe RPC to insert `video_outputs`, create a pending hash-bound `approvals` row, and advance the job to `awaiting_owner`.

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
8. A changed or mismatched stored output hash is rejected; approval is bound to the exact output version/hash.
9. A failed DB finalization leaves the output private and unapproved for recovery; orphan cleanup remains to be automated.
10. Test with a real, authorized gameplay clip and final voiceover; synthetic CI media is not sufficient.

## Remaining implementation sequence

1. Complete the job creation/status endpoint and owner-scoped manifest validation, then review/apply the staged migration. The table is not deployed yet.
2. Complete automated tests for the worker-only output upload/finalization path and verify the migration against a disposable database before deployment.
3. Add authenticated app-side RPCs/UI to create render jobs, show progress, preview private outputs, and collect hash-bound approval.
4. Add orphan cleanup and a controlled recovery path for failed uploads/finalization.
5. Run end-to-end tests with real authorized gameplay and an approved voiceover.
6. Review security findings and deployment settings; keep the existing draft PR unmerged until explicitly approved.

## Dynamic asset handoff implementation (staged, not deployed)

A new Edge Function source file is staged at `supabase/functions/gcf-render-job-assets/index.ts`. It is intentionally separate from the live legacy `gcf-render-assets` function, so no production behavior is replaced.

### Request and response contract

- Method: POST; authorization: a GitHub Actions OIDC identity token with audience `gcf-render-job-assets`. The function verifies the issuer/signature and restricts repository ID, owner actor ID, workflow file, and allowed branch refs; no shared bearer secret is needed.
- Request body: `{ "job_id": "<render_jobs UUID>" }`. The response also carries the job's output type, destination platform, and aspect ratio.
- The function reads the job from `render_jobs`, then resolves only assets whose owner and package match that job.
- Manifest entries use `{ "asset_id": "<media_assets UUID>", "file_name": "scene-01.mp4" }`.
- Accepted source roles: `gameplay`, `trailer`, exactly one `voiceover`, and optional `music`.
- Gameplay/trailer assets must be approved MP4s; voiceover and music must be WAV files.
- Every source-backed gameplay/trailer/music asset (and any source-backed voiceover) must have `media_assets.rights_status='approved'` and the latest matching `rights_reviews` row must be `approved_by_owner`, with commercial use, derivatives, redistribution, game-policy and third-party checks, owner review evidence, and a non-expired license. Music additionally requires `music_rights_verified=true`.
- Only private `gcf-source-media` objects beneath the job owner's storage prefix are signed. Every asset must carry a valid SHA-256. URLs expire after 10 minutes. Responses are no-store. The function evaluates the most recent review per source and returns the rights evidence required by the FFmpeg renderer.
- The function does not publish, mutate approval state, or mark a render job complete. `.github/workflows/render-job.yml` stages a manual OIDC-protected workflow that fetches the signed assets, verifies SHA-256, builds the renderer rights manifest, renders, runs `render/quality_check.py`, and produces a one-day review artifact. It does not yet upload the final MP4 to Supabase.

### Deployment gate

This source depends on the staged `render_jobs` migration. It must be type-checked in CI, reviewed, and deployed only after the migration is applied and a controlled authenticated test succeeds. The function is not deployed to Supabase yet. CI runs `deno check` against this source and synthetic FFmpeg/QC acceptance tests.


## Private output upload and atomic finalization (staged, not deployed)

- `supabase/functions/gcf-render-job-output/index.ts` accepts only GitHub OIDC tokens for the repository, owner actor, exact workflow file, and allowed branch. Its audience is `gcf-render-job-output`.
- `prepare_upload` moves the job into `uploading`, generates a unique owner/package/job-scoped MP4 path, and returns a signed upload token for the private `gcf-video-outputs` bucket.
- `render/upload_supabase_tus.py` uses the signed token with Supabase's resumable TUS endpoint and 6 MiB chunks. The token is held in runner memory/environment only; it is not a workflow input, artifact, or log value. Two local mocked uploader tests pass, including a multi-chunk transfer and rejection of a path outside the owner/package/job prefix.
- `finalize` downloads the private object server-side, checks the byte count and SHA-256 against the QC report, and calls `gcf_finalize_render_job_output`.
- The SQL RPC runs as `SECURITY INVOKER` and is executable only by `service_role`. In one database transaction it creates `video_outputs`, creates a pending `approvals` row bound to the output version and hash, and changes the job to `awaiting_owner`. A repeated identical finalization is idempotent.
- Current bucket limit is 50 MiB. The QC helper blocks larger outputs. No real output has been uploaded and this code has not been deployed or executed against the live project.
