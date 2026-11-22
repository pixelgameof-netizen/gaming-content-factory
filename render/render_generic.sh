#!/usr/bin/env bash
set -euo pipefail
# Reusable FFmpeg renderer. Requires approved clips and final narration.
EPISODE="${1:?Usage: render_generic.sh <episode> <vertical|horizontal> [output.mp4]}"
FORMAT="${2:?Format must be vertical or horizontal}"
OUTPUT="${3:-artifacts/${EPISODE}.mp4}"
ROOT="production/${EPISODE}"
MEDIA="${ROOT}/media"
RIGHTS="${ROOT}/rights-review.json"

case "$FORMAT" in
  vertical) WIDTH=1080; HEIGHT=1920; RATIO="9:16" ;;
  horizontal) WIDTH=1920; HEIGHT=1080; RATIO="16:9" ;;
  *) echo "Unsupported format: $FORMAT" >&2; exit 2 ;;
esac
command -v ffmpeg >/dev/null || { echo "FFmpeg missing" >&2; exit 1; }
command -v ffprobe >/dev/null || { echo "FFprobe missing" >&2; exit 1; }
[[ -f "$RIGHTS" && -d "$MEDIA" ]] || { echo "Missing rights review or media directory" >&2; exit 1; }
python3 - "$RIGHTS" "$MEDIA" <<'PY'
import json, pathlib, sys
doc=json.loads(pathlib.Path(sys.argv[1]).read_text())
media=pathlib.Path(sys.argv[2])
assets=doc.get("assets", [])
if not assets: raise SystemExit("rights-review.json needs an assets array")
for a in assets:
    f=a.get("file")
    if not f or not (media/f).is_file(): raise SystemExit(f"Missing asset: {f}")
    if a.get("status")!="approved" or a.get("commercial_use") is not True:
        raise SystemExit(f"Asset not approved for commercial use: {f}")
    if not a.get("source_url") or not a.get("license_url") or not a.get("reviewed_by"):
        raise SystemExit(f"Missing rights evidence: {f}")
PY
mapfile -t SCENES < <(find "$MEDIA" -maxdepth 1 -type f -name 'scene-*.mp4' | sort -V)
(("${#SCENES[@]}" >= 1)) || { echo "No scene-*.mp4 files" >&2; exit 1; }
[[ -f "$MEDIA/voiceover.wav" ]] || { echo "Final voiceover.wav required" >&2; exit 1; }

mkdir -p "$(dirname "$OUTPUT")"
INPUTS=()
FILTER=""
for f in "${SCENES[@]}"; do INPUTS+=( -i "$f" ); done
N="${#SCENES[@]}"
for ((i=0;i<N;i++)); do
  FILTER+="[${i}:v]scale=${WIDTH}:${HEIGHT}:force_original_aspect_ratio=increase,crop=${WIDTH}:${HEIGHT},setsar=1,fps=30,format=yuv420p[v${i}];"
done
for ((i=0;i<N;i++)); do FILTER+="[v${i}]"; done
FILTER+="concat=n=${N}:v=1:a=0[vout]"
INPUTS+=( -i "$MEDIA/voiceover.wav" )
AUDIO_INDEX=$N
if [[ -f "$MEDIA/music.wav" ]]; then
  INPUTS+=( -i "$MEDIA/music.wav" )
  MUSIC_INDEX=$((N+1))
  AUDIO="[${AUDIO_INDEX}:a]aresample=48000,volume=1.0[voice];[${MUSIC_INDEX}:a]aresample=48000,volume=0.12[music];[voice][music]amix=inputs=2:duration=first:dropout_transition=2[aout]"
else
  AUDIO="[${AUDIO_INDEX}:a]aresample=48000,volume=1.0[aout]"
fi
ffmpeg -hide_banner -y "${INPUTS[@]}" -filter_complex "$FILTER;$AUDIO" \
  -map '[vout]' -map '[aout]' -c:v libx264 -preset veryfast -crf 20 \
  -pix_fmt yuv420p -c:a aac -b:a 192k -ar 48000 -movflags +faststart "$OUTPUT"

if [[ -f "$MEDIA/captions.srt" ]]; then
  TEMP="${OUTPUT%.mp4}.captioned.mp4"
  ffmpeg -hide_banner -y -i "$OUTPUT" -vf "subtitles=$MEDIA/captions.srt" \
    -c:v libx264 -preset veryfast -crf 20 -c:a copy -movflags +faststart "$TEMP"
  mv "$TEMP" "$OUTPUT"
fi
DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$OUTPUT")
DIMENSIONS=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$OUTPUT")
[[ "$DIMENSIONS" == "${WIDTH}x${HEIGHT}" ]] || { echo "Unexpected dimensions: $DIMENSIONS" >&2; exit 1; }
python3 - "$DURATION" <<'PY'
import sys
d=float(sys.argv[1])
if d <= 1 or d > 900: raise SystemExit(f"Duration outside allowed range: {d}")
PY
sha256sum "$OUTPUT" | tee "${OUTPUT}.sha256"
printf 'Rendered: %s\nFormat: %s\nDimensions: %s\nDuration: %s\n' "$OUTPUT" "$RATIO" "$DIMENSIONS" "$DURATION"
