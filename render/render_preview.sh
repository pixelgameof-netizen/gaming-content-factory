#!/usr/bin/env bash
set -euo pipefail

OUTPUT="${1:-preview.mp4}"
DURATION=12
FONT="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "FFmpeg is required." >&2
  exit 1
fi
if [[ ! -f "$FONT" ]]; then
  echo "Expected font not found: $FONT" >&2
  exit 1
fi

# Original motion-graphics test only: no GTA footage, third-party clips, or music.
ffmpeg -hide_banner -y \
  -f lavfi -i "color=c=0x101827:s=720x1280:r=30:d=${DURATION}" \
  -f lavfi -i "sine=frequency=110:sample_rate=48000:duration=${DURATION}" \
  -filter_complex "[0:v]drawbox=x=0:y=0:w=720:h=12:color=0x35c6c8:t=fill,drawtext=fontfile=${FONT}:text='GAMING CONTENT FACTORY':fontcolor=white:fontsize=30:x=(w-text_w)/2:y=420,drawtext=fontfile=${FONT}:text='CLOUD RENDER TEST':fontcolor=0x35c6c8:fontsize=42:x=(w-text_w)/2:y=500,drawtext=fontfile=${FONT}:text='VERTICAL 9\:16  |  30 FPS':fontcolor=white:fontsize=23:x=(w-text_w)/2:y=575,drawtext=fontfile=${FONT}:text='Preview only - not the final GTA VI Short':fontcolor=0xb8c4d6:fontsize=18:x=(w-text_w)/2:y=1120,fade=t=in:st=0:d=0.5,fade=t=out:st=11:d=1[v]" \
  -map "[v]" -map 1:a \
  -c:v libx264 -preset veryfast -crf 24 -pix_fmt yuv420p \
  -c:a aac -b:a 96k -shortest -movflags +faststart "$OUTPUT"

echo "Created $OUTPUT"
