#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-production/short-01}"
OUT="${2:-short-01-preview.mp4}"
DURATION="10.2"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

command -v ffmpeg >/dev/null 2>&1 || { echo "FFmpeg is required." >&2; exit 1; }
command -v ffprobe >/dev/null 2>&1 || { echo "ffprobe is required." >&2; exit 1; }

for n in 01 02 03 04 05; do
  f="$ROOT/media/scene-$n.mp4"
  [[ -s "$f" ]] || { echo "Missing approved scene file: $f" >&2; exit 2; }
done
VO="$ROOT/media/voiceover.wav"
[[ -s "$VO" ]] || { echo "Missing final narration: $VO" >&2; exit 2; }
[[ -s "$ROOT/captions.srt" ]] || { echo "Missing captions.srt" >&2; exit 2; }

# Normalize all five scenes to a consistent vertical timeline.
for n in 01 02 03 04 05; do
  ffmpeg -hide_banner -loglevel error -y \
    -stream_loop -1 -i "$ROOT/media/scene-$n.mp4" -t "$DURATION" \
    -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1,format=yuv420p" \
    -an -c:v libx264 -preset veryfast -crf 20 "$TMP/scene-$n.mp4"
done

{
  for n in 01 02 03 04 05; do
    printf "file '%s/scene-%s.mp4'\n" "$TMP" "$n"
  done
} > "$TMP/concat.txt"

ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i "$TMP/concat.txt" \
  -c copy "$TMP/picture.mp4"

# Burn readable Spanish captions and apply subtle opening/closing fades.
# Music is optional; narration remains the required primary audio.
CAPTIONS="$ROOT/captions.srt"
VF="subtitles=$CAPTIONS:force_style='FontName=DejaVu Sans,FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00101010,BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV=170'"
if [[ -s "$ROOT/media/music.wav" ]]; then
  ffmpeg -hide_banner -y -i "$TMP/picture.mp4" -i "$VO" -i "$ROOT/media/music.wav" \
    -filter_complex "[0:v]$VF,fade=t=in:st=0:d=0.35,fade=t=out:st=50.5:d=0.5[v];[1:a]atrim=0:51,asetpts=PTS-STARTPTS,volume=1.0[vo];[2:a]atrim=0:51,asetpts=PTS-STARTPTS,volume=0.12[music];[vo][music]amix=inputs=2:duration=first:dropout_transition=2[a]" \
    -map "[v]" -map "[a]" -t 51 -r 30 -c:v libx264 -preset veryfast -crf 19 -pix_fmt yuv420p \
    -c:a aac -b:a 192k -movflags +faststart "$OUT"
else
  ffmpeg -hide_banner -y -i "$TMP/picture.mp4" -i "$VO" \
    -vf "$VF,fade=t=in:st=0:d=0.35,fade=t=out:st=50.5:d=0.5" \
    -map 0:v:0 -map 1:a:0 -t 51 -r 30 -c:v libx264 -preset veryfast -crf 19 -pix_fmt yuv420p \
    -af "atrim=0:51,asetpts=PTS-STARTPTS" -c:a aac -b:a 192k -movflags +faststart "$OUT"
fi

ffprobe -v error -show_entries format=duration:stream=codec_type,width,height,r_frame_rate \
  -of json "$OUT"
echo "Created preview: $OUT"
echo "This output is a preview. Verify narration sync, media rights, captions, and visual quality before approval."
