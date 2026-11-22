# Private Supabase → GitHub Actions media connection

## What is deployed
- Edge Function: `gcf-render-assets`
- Project: `pyrrcfegucvxyxlxzowu`
- It accepts only POST requests for `short-01`.
- It signs only six fixed object names under this owner folder in the private `gcf-source-media` bucket:
  `ddfe2f5e-c5da-418c-b84c-60c8be6f7414/short-01/media/`
- Signed URLs expire after 10 minutes and are never written to logs or Git.
- The function cannot accept arbitrary bucket names or object paths.

## One-time manual key setup
Supabase and GitHub credentials are deliberately not written by automation into this public repository.

1. In Supabase Dashboard → Settings → API Keys, create a **new Secret API key** named exactly `gcf-render`. Do not use the default secret key or legacy service_role key.
2. In GitHub → `pixelgameof-netizen/gaming-content-factory` → Settings → Secrets and variables → Actions → New repository secret, create:
   - Name: `SUPABASE_RENDER_KEY`
   - Value: the newly created `gcf-render` secret key
3. Never paste the key into chat, a file, an issue, a commit, or a workflow log. Rotate/revoke this key if it is exposed.

The Edge Function validates that named key with Supabase's `withSupabase({ auth: "secret:gcf-render" })` middleware. Its elevated key is held by Supabase's runtime; GitHub receives only the short-lived file URLs returned for the six hard-coded assets.

## Upload layout
Upload only reviewed media into the private bucket:
`gcf-source-media/<owner-id>/short-01/media/`

Required object names:
- `scene-01.mp4` … `scene-05.mp4`
- `voiceover.wav`

The five clips and narration must first be marked approved in `rights-review.json`. The workflow stops before contacting Supabase if any rights approval is missing.

## Important current state
The bucket is private and currently has zero objects. No media has been uploaded. The workflow is manual-only and does not publish to the public repository or any social platform. It uploads a GitHub Actions artifact with one-day retention only after all checks pass.
