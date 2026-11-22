#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-production/short-01}"
: "${SUPABASE_FUNCTION_URL:?SUPABASE_FUNCTION_URL is required}"
: "${SUPABASE_RENDER_KEY:?SUPABASE_RENDER_KEY is required}"
command -v curl >/dev/null
command -v jq >/dev/null

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$ROOT/media"

# Do not print the response: it contains short-lived signed URLs.
HTTP_CODE="$(curl -sS -o "$TMP/response.json" -w '%{http_code}' \
  -X POST "$SUPABASE_FUNCTION_URL" \
  -H "apikey: $SUPABASE_RENDER_KEY" \
  -H 'Content-Type: application/json' \
  --data '{"episode":"short-01"}')"

if [[ "$HTTP_CODE" != "200" ]]; then
  echo "Supabase asset gateway returned HTTP $HTTP_CODE." >&2
  jq -r '.error // "Asset request failed", (.missing // [] | join(", "))' "$TMP/response.json" >&2 || true
  exit 1
fi

for name in scene-01.mp4 scene-02.mp4 scene-03.mp4 scene-04.mp4 scene-05.mp4 voiceover.wav; do
  url="$(jq -er --arg name "$name" '.files[$name]' "$TMP/response.json")"
  curl --fail --silent --show-error --location "$url" -o "$ROOT/media/$name"
  test -s "$ROOT/media/$name"
done

echo "Downloaded 5 approved-scene inputs and the narration input from private Storage."
