# Private Supabase → GitHub Actions media connection

## Deployed endpoint
- Edge Function: `gcf-render-assets`
- URL: `https://pyrrcfegucvxyxlxzowu.supabase.co/functions/v1/gcf-render-assets`
- Project: `pyrrcfegucvxyxlxzowu`
- It accepts only POST requests for `short-01`.
- It signs only six fixed object names under this owner folder in the private `gcf-source-media` bucket:
  `ddfe2f5e-c5da-418c-b84c-60c8be6f7414/short-01/media/`
- Signed URLs expire after 10 minutes and are never written to logs or Git.
- The function cannot accept arbitrary bucket names or object paths.

## One-time secret setup
The GitHub runner must **not** receive a Supabase Secret API key. The function keeps the Supabase server key inside Supabase and uses a separate, limited gateway token.

1. Generate a random token of at least 32 bytes using a password manager or trusted local secret generator. Do not paste it into ChatGPT.
2. In Supabase Dashboard → Edge Functions → Secrets, add:
   - Name: `GCF_RENDER_GATEWAY_TOKEN`
   - Value: the generated random token
3. In GitHub → `pixelgameof-netizen/gaming-content-factory` → Settings → Secrets and variables → Actions → New repository secret, add the exact same value:
   - Name: `GCF_RENDER_GATEWAY_TOKEN`
   - Value: the same generated token
4. Never commit or log this token. Rotate it in both places if exposed.

The function checks this token before doing anything. Its elevated Supabase key remains in Supabase's injected server environment; GitHub only receives six signed download URLs that expire after 10 minutes.

## Upload layout
Upload only reviewed media into the private bucket:
`gcf-source-media/<owner-id>/short-01/media/`

Required object names:
- `scene-01.mp4` … `scene-05.mp4`
- `voiceover.wav`

The five clips and narration must first be marked approved in `rights-review.json`. The workflow stops before contacting Supabase if any rights approval is missing.

## Current state
The bucket is private and currently has zero objects. No media has been uploaded. The workflow is manual-only and does not publish to the public repository or any social platform. It uploads a GitHub Actions artifact with one-day retention only after all checks pass.
