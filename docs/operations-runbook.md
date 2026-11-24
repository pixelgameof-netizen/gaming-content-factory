# Operations runbook

Last reviewed: 2026-11-24

## Purpose

This runbook describes the current operating path for Gaming Content Factory. It distinguishes automated discovery, owner review, rendering, and publication approval. A successful workflow run is not proof that a finished video exists.

## Current workflow map

| Workflow | Trigger | What it does | What it does not do |
|---|---|---|---|
| `gameplay-hunter.yml` | Daily schedule, manual dispatch, relevant push | Searches Commons for candidate videos, filters the configured license allowlist, stores candidate metadata, stages and inspects the currently curated Minecraft source set, uploads review artifacts | Does not approve rights, create render jobs, or publish |
| `render-job.yml` | Every 10 minutes, manual dispatch | Claims a queued render job, obtains approved source assets using GitHub OIDC, generates narration if script text is supplied, renders, runs QC, uploads the MP4 to private Supabase Storage, registers it for owner review | Does not create a job when the queue is empty; does not publish |
| `test-tts.yml` | Relevant push, pull request, manual dispatch | Verifies Spanish Kokoro narration and SRT generation | Does not render a production video |
| `test-render-generic.yml` | Relevant push, pull request, manual dispatch | Verifies the generic FFmpeg renderer with synthetic media | Does not validate source rights or a real production package |

## Latest infrastructure verification

- The five curated Minecraft media assets remain in private storage with `rights_status='approved'`; their five rights reviews are `approved_by_owner`.
- The staging Edge Function is idempotent for already-approved assets: it reports them as `already_approved` instead of trying to re-review them as new candidates.
- The Hunter workflow skips the fixed Minecraft staging/inspection path when the requested game list does not include Minecraft.
- Discovery now reads `config/game_profiles.json`, searches configured aliases for six initial games, and falls back to the exact custom game name. Each game is capped at eight candidates; all results remain unapproved metadata.
- If some curated assets are already approved and others still need technical inspection, the workflow expects inspection only for the remaining assets.
- The Supabase migration `202611240001_render_job_fk_indexes_and_rls_initplan.sql` has been applied. It adds covering indexes for render-job foreign keys and uses a scalar subquery for the owner RLS check.
- The approval RPC contract has regression tests for authenticated ownership, exact output/version/hash/platform matching, pending-only decisions, and restricted execution grants.

## First production: Minecraft

The first package has an owner-approved Spanish script and five owner-approved source/rights records. The source clips are stored in the private source bucket. The approval is based on the reviewed evidence and is not a legal guarantee for independent third-party rights.

### Required sequence

1. In the Floot application, sign in as the owner.
2. Open the approved Minecraft package and create its render job using the application action. Do not bypass owner authentication with direct SQL or a service-role shortcut.
3. Confirm that the job appears in the render queue.
4. Wait for `render-job.yml` to claim the queued job, or dispatch that workflow manually if the normal worker schedule is not progressing.
5. Inspect the workflow logs and the private output registration. A worker run that says `No queued render jobs.` is a successful idle run, not a completed render.
6. Open the private output in the application and review the complete MP4 on mobile and desktop.
7. Verify narration, captions, scene order, transitions, framing, audio, duration, attribution, and the QC report.
8. Approve only the exact MP4 and SHA-256 shown by the application. If the bytes change, repeat review and approval.

## Owner approval lifecycle

The approval layer is hash-bound and owner-scoped:

1. The render worker registers a verified MP4 in private `gcf-video-outputs` and creates an `approvals` row with `status='pending'`.
2. The app lists pending approvals through `gcf_list_pending_approvals`. The RPC filters by `auth.uid()`; it does not expose another owner's outputs.
3. The app must display the exact output version, SHA-256, platform, aspect ratio, duration, quality status, and private preview. The owner should review the actual video, not just the workflow log or QC report.
4. An approve/reject action must call `gcf_decide_render_output` with the approval ID, output ID, SHA-256, platform, and decision. The RPC checks the authenticated owner and exact version/hash/platform, and requires `quality_status='passed'` and the private output bucket.
5. A repeated identical decision is idempotent. A conflicting second decision is rejected. A changed MP4 hash requires a new output version and new approval.
6. Approval is not publication. There is no automatic publishing step in this pipeline.

### Required app behavior still to verify

- Show a playable private preview, not a public storage URL.
- Display the full SHA-256 and a clear version label.
- Provide separate approve and reject actions, with an optional note.
- Confirm the result returned by the RPC and refresh the pending list.
- Never show an approval button for a missing, rejected, or non-passing output.
- Make the owner explicitly confirm before approving; do not treat opening or playing a video as approval.

## Current acceptance criteria

- Final MP4 is H.264 video + AAC audio in the requested dimensions.
- QC report passes; SHA-256 is calculated and retained.
- Narration is generated from the owner-approved script; captions correspond to generated speech.
- Gameplay remains legible in vertical framing; important HUD/gameplay edges are not cropped unnecessarily.
- Source attribution and license links are included in the final credit treatment or accompanying metadata as appropriate.
- Output is stored in the private output bucket and accessible only through the authenticated app flow.
- The owner can review the output from a phone and a desktop browser.
- No publishing action occurs without separate, explicit approval of the exact output hash.

## Known gaps before declaring the whole platform complete

1. **Real end-to-end render:** no production MP4 has yet been confirmed in the output bucket.
2. **Multi-game staging:** discovery now uses configurable aliases for six initial titles and supports custom game names. Automatic private staging and technical inspection still use the curated Minecraft source set; non-Minecraft candidates remain review-only until a game-specific rights and staging adapter is implemented.
3. **Candidate-to-package workflow:** validate that a selected candidate can be reviewed, downloaded/staged privately, attached to a package, and rendered without manual database operations.
4. **Mobile/desktop review:** verify playback, metadata, attribution, hash display, and owner approval in the live authenticated app.
5. **Reliability:** test duplicate claims, transient download/upload failures, invalid source files, retry behavior, and multiple queued jobs.
6. **Security posture:** review repository visibility and Supabase security advisories; do not weaken RLS or owner checks to make the workflow appear functional.
7. **Operational notifications:** add owner-facing success/failure notifications only after the app's authenticated workflow and notification channel are verified.
8. **Documentation:** keep this runbook and README synchronized with actual deployed behavior.

## Troubleshooting

- **Worker succeeds but no video appears:** inspect the log for `No queued render jobs.`; create the job through the authenticated app first.
- **TTS fails:** inspect the TTS workflow separately before changing renderer dependencies. The latest known Spanish TTS test passed on 2026-11-24.
- **Synthetic render passes but production fails:** inspect the render job's claim response, asset MIME/name mapping, SHA-256 verification, rights manifest, FFmpeg log, QC report, and private upload registration.
- **A candidate is rejected:** do not bypass the license, publisher-policy, third-party asset, or owner-review gates. Find a different candidate or obtain independent permission.
- **The preview or app action is unavailable:** check Floot project quota and owner session; do not replace the owner-authenticated app action with privileged database writes.

## Definition of done

The platform is complete only after a real production is generated and reviewed, the complete candidate-to-private-output lifecycle works for more than one game, mobile and desktop access are verified, failure recovery is tested, and publishing remains behind an explicit hash-bound owner approval.
