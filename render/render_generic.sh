#!/usr/bin/env bash
set -euo pipefail
EPISODE="$1"
FORMAT="$2"
OUTPUT="$3"
[[ -n "$OUTPUT" ]] || OUTPUT="artifacts/$EPISODE.mp4"
[[ "$EPISODE" =~ ^[a-zA-Z0-9][a-zA-Z0-9_-]{0,49}$ ]] || { echo "Invalid episode name" >&2; exit 2; }
ROOT="production/$EPISODE"
MEDIA="$ROOT/media"
RIGHTS="$ROOT/rights-review.json"
VISUAL_DIR="$ROOT/visual"
FONT="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

case "$FORMAT" in
  vertical)
    WIDTH=1080; HEIGHT=1920; RATIO="9:16"
    CAPTION_STYLE="FontName=DejaVu Sans,FontSize=10,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&HCC000000,BorderStyle=1,Outline=1,Shadow=1,Alignment=2,MarginL=30,MarginR=30,MarginV=40"
    ;;
  horizontal)
    WIDTH=1920; HEIGHT=1080; RATIO="16:9"
    CAPTION_STYLE="FontName=DejaVu Sans,FontSize=13,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&HCC000000,BorderStyle=1,Outline=1,Shadow=1,Alignment=2,MarginL=24,MarginR=24,MarginV=22"
    ;;
  *) echo "Unsupported format: $FORMAT" >&2; exit 2 ;;
esac

command -v ffmpeg >/dev/null || { echo "FFmpeg missing" >&2; exit 1; }
command -v ffprobe >/dev/null || { echo "FFprobe missing" >&2; exit 1; }
[[ -f "$RIGHTS" && -d "$MEDIA" ]] || { echo "Missing rights review or media directory" >&2; exit 1; }
[[ -f "$FONT" ]] || { echo "Editorial font is missing: $FONT" >&2; exit 1; }

python3 - "$RIGHTS" "$MEDIA" <<'PY'
import json, pathlib, sys
doc=json.loads(pathlib.Path(sys.argv[1]).read_text())
media=pathlib.Path(sys.argv[2])
assets=doc.get("assets", [])
scene_files={p.name for p in media.glob("scene-*.mp4") if p.is_file()}
approved_files=set()
if not assets: raise SystemExit("rights-review.json needs an assets array")
for a in assets:
    f=a.get("file")
    if not isinstance(f, str) or pathlib.PurePath(f).name != f or not f.endswith(".mp4"):
        raise SystemExit(f"Invalid asset filename: {f}")
    if f not in scene_files: raise SystemExit(f"Missing asset: {f}")
    approved_files.add(f)
    if a.get("status")!="approved" or a.get("commercial_use_confirmed") is not True:
        raise SystemExit(f"Asset not approved for commercial use: {f}")
    if a.get("publisher_policy_verified") is not True or a.get("third_party_assets_verified") is not True or a.get("reviewer_approved") is not True or a.get("music_rights_verified") is not True:
        raise SystemExit(f"Human review incomplete: {f}")
    if not a.get("source_url") or not a.get("license_url"):
        raise SystemExit(f"Missing rights evidence: {f}")
unreviewed=scene_files-approved_files
if unreviewed: raise SystemExit("Scene files missing explicit rights approval: "+", ".join(sorted(unreviewed)))
voice=doc.get("voiceover", {})
if voice.get("status")!="approved" or voice.get("rights_confirmed") is not True or voice.get("reviewer_approved") is not True:
    raise SystemExit("Voiceover rights and human approval are required")
music=doc.get("music", {})
if (media/"music.wav").is_file():
    if music.get("status")!="approved" or music.get("rights_confirmed") is not True or music.get("reviewer_approved") is not True:
        raise SystemExit("Music rights and human approval are required")
PY

mapfile -t SCENES < <(find "$MEDIA" -maxdepth 1 -type f -name 'scene-*.mp4' | sort -V)
N="${#SCENES[@]}"
((N >= 1)) || { echo "No scene-*.mp4 files" >&2; exit 1; }
[[ -f "$MEDIA/voiceover.wav" ]] || { echo "Final voiceover.wav required" >&2; exit 1; }

mkdir -p "$(dirname "$OUTPUT")" "$VISUAL_DIR"
PROFILE="$ROOT/visual-profile.json"
if [[ ! -f "$PROFILE" ]]; then
  printf '%s\n' '{"game_title":"GAME FILE","topic":"HISTORIAS Y MOMENTOS DEL UNIVERSO GAMING","chapters":[]}' > "$PROFILE"
fi

python3 - "$PROFILE" "$VISUAL_DIR" "$N" <<'PY'
import json, pathlib, re, sys
profile_path, out_dir, count = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), int(sys.argv[3])
p=json.loads(profile_path.read_text(encoding="utf-8"))
out_dir.mkdir(parents=True, exist_ok=True)
def clean(value, default, limit):
    value=" ".join(str(value or default).replace("\n"," ").split())
    value=re.sub(r"[\x00-\x1f]", "", value)
    return value[:limit].strip() or default
def write(name, value):
    (out_dir/name).write_text(value, encoding="utf-8")
game=clean(p.get("game_title") or p.get("headline"), "GAME FILE", 30).upper()
kicker=clean(p.get("kicker"), "PIXEL GAME  /  HISTORIA GAMING", 48).upper()
subhead=clean(p.get("subhead") or p.get("topic"), "HISTORIAS Y MOMENTOS QUE CAMBIARON LOS JUEGOS", 64).upper()
cta=clean(p.get("cta"), "COMENTA TU MOMENTO FAVORITO", 48).upper()
write("kicker.txt", kicker)
write("game.txt", game)
write("subhead.txt", subhead)
write("cta.txt", cta)
raw=p.get("chapters") if isinstance(p.get("chapters"), list) else []
for i in range(count):
    fallback=f"ETAPA {i+1:02d}"
    label=clean(raw[i] if i < len(raw) else fallback, fallback, 20).upper()
    write(f"chapter-{i}.txt", label)
    write(f"stage-{i}.txt", label)
PY

INPUTS=()
FILTER=""
for f in "${SCENES[@]}"; do INPUTS+=( -i "$f" ); done
VOICE_DURATION="$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$MEDIA/voiceover.wav")"
TRANSITION_DURATION="0.25"
SEGMENT_DURATION="$(awk -v duration="$VOICE_DURATION" -v count="$N" -v transition="$TRANSITION_DURATION" 'BEGIN { if (count < 1 || duration <= 0) exit 1; printf "%.3f", (duration+(count-1)*transition)/count }')"

if [[ "$FORMAT" == "vertical" ]]; then
  GAME_LENGTH="$(wc -m < "$VISUAL_DIR/game.txt")"
  TITLE_SIZE=78
  if (( GAME_LENGTH > 16 )); then TITLE_SIZE=62; fi
  if (( GAME_LENGTH > 22 )); then TITLE_SIZE=50; fi
fi

for ((i=0;i<N;i++)); do
  if [[ "$FORMAT" == "vertical" ]]; then
    FILTER+="[$i:v]split=2[bg$i][fg$i];"
    FILTER+="[bg$i]scale=$WIDTH:$HEIGHT:force_original_aspect_ratio=increase,crop=$WIDTH:$HEIGHT,boxblur=24:12,eq=brightness=-0.14:saturation=0.95[blur$i];"
    FILTER+="[fg$i]scale=$WIDTH:$HEIGHT:force_original_aspect_ratio=decrease[fit$i];"
    FILTER+="[blur$i][fit$i]overlay=(W-w)/2:(H-h)/2[base$i];"
    DECOR="drawbox=x=48:y=112:w=984:h=410:color=black@0.34:t=fill,"
    DECOR+="drawbox=x=48:y=112:w=9:h=410:color=0x9DFF42@0.95:t=fill,"
    DECOR+="drawtext=fontfile=$FONT:textfile=$VISUAL_DIR/kicker.txt:fontcolor=0xC8F2A0:fontsize=21:x=82:y=148:shadowcolor=black@0.65:shadowx=2:shadowy=2,"
    DECOR+="drawtext=fontfile=$FONT:textfile=$VISUAL_DIR/game.txt:fontcolor=white:fontsize=$TITLE_SIZE:line_spacing=8:x=82:y=210:shadowcolor=black@0.7:shadowx=2:shadowy=3,"
    DECOR+="drawtext=fontfile=$FONT:textfile=$VISUAL_DIR/subhead.txt:fontcolor=0xE0E7E8:fontsize=27:x=84:y=356:shadowcolor=black@0.7:shadowx=2:shadowy=2,"
    TRACK_X=70; TRACK_W=940; GAP=10
    SEG_W=$(((TRACK_W-GAP*(N-1))/N))
    for ((j=0;j<N;j++)); do
      X=$((TRACK_X+j*(SEG_W+GAP)))
      DECOR+="drawbox=x=$X:y=468:w=$SEG_W:h=8:color=white@0.25:t=fill,"
      if ((j==i)); then
        DECOR+="drawbox=x=$X:y=468:w=$SEG_W:h=8:color=0x9DFF42@0.98:t=fill,"
      fi
      if ((N<=6)); then
        if ((j==i)); then LABEL_COLOR="0xC8F2A0"; else LABEL_COLOR="0xE5E7EB"; fi
        DECOR+="drawtext=fontfile=$FONT:textfile=$VISUAL_DIR/chapter-$j.txt:fontcolor=$LABEL_COLOR:fontsize=17:x=$X:y=492:shadowcolor=black@0.7:shadowx=1:shadowy=1,"
      fi
    done
    DECOR+="drawbox=x=0:y=626:w=1080:h=3:color=white@0.72:t=fill,"
    DECOR+="drawbox=x=48:y=1310:w=984:h=310:color=black@0.30:t=fill,"
    DECOR+="drawbox=x=48:y=1310:w=9:h=310:color=0x9DFF42@0.95:t=fill,"
    DECOR+="drawtext=fontfile=$FONT:text='ETAPA '$(printf '%02d' "$((i+1))")' / '$(printf '%02d' "$N"):fontcolor=0xC8F2A0:fontsize=22:x=82:y=1350:shadowcolor=black@0.7:shadowx=1:shadowy=1,"
    DECOR+="drawtext=fontfile=$FONT:textfile=$VISUAL_DIR/stage-$i.txt:fontcolor=white:fontsize=58:x=82:y=1400:shadowcolor=black@0.75:shadowx=2:shadowy=3,"
    if ((i==N-1)); then
      DECOR+="drawtext=fontfile=$FONT:textfile=$VISUAL_DIR/cta.txt:fontcolor=0xE5F5D5:fontsize=24:x=84:y=1510:shadowcolor=black@0.75:shadowx=1:shadowy=2,"
    else
      DECOR+="drawtext=fontfile=$FONT:text='LA HISTORIA SIGUE':fontcolor=0xB8C2C8:fontsize=20:x=84:y=1512:shadowcolor=black@0.7:shadowx=1:shadowy=1,"
    fi
    DECOR+="drawbox=x=70:y=1788:w=940:h=2:color=white@0.28:t=fill,"
    DECOR+="drawtext=fontfile=$FONT:text='PIXEL GAME  /  ARCHIVO GAMING':fontcolor=0xD1D9D9:fontsize=17:x=70:y=1810:shadowcolor=black@0.6:shadowx=1:shadowy=1"
    FILTER+="[base$i]$DECOR,trim=duration=$SEGMENT_DURATION,tpad=stop_mode=clone:stop_duration=$SEGMENT_DURATION,trim=duration=$SEGMENT_DURATION,setpts=PTS-STARTPTS,setsar=1,fps=30,settb=AVTB,format=yuv420p[v$i];"
  else
    FILTER+="[$i:v]scale=$WIDTH:$HEIGHT:force_original_aspect_ratio=increase,crop=$WIDTH:$HEIGHT,"
    FILTER+="trim=duration=$SEGMENT_DURATION,tpad=stop_mode=clone:stop_duration=$SEGMENT_DURATION,trim=duration=$SEGMENT_DURATION,setpts=PTS-STARTPTS,setsar=1,fps=30,settb=AVTB,format=yuv420p[v$i];"
  fi
done

if ((N == 1)); then
  FILTER+="[v0]format=yuv420p[vout]"
else
  PREVIOUS="[v0]"
  for ((i=1;i<N;i++)); do
    OFFSET="$(awk -v segment="$SEGMENT_DURATION" -v transition="$TRANSITION_DURATION" -v count="$i" 'BEGIN { printf "%.3f", count*(segment-transition) }')"
    TRANSITION="fade"
    if [[ "$FORMAT" == "vertical" ]]; then TRANSITION="pixelize"; fi
    FILTER+="$PREVIOUS[v$i]xfade=transition=$TRANSITION:duration=$TRANSITION_DURATION:offset=$OFFSET[x$i];"
    PREVIOUS="[x$i]"
  done
  FILTER+="$PREVIOUS"format=yuv420p[vout]
fi

INPUTS+=( -i "$MEDIA/voiceover.wav" )
AUDIO_INDEX=$N
if [[ -f "$MEDIA/music.wav" ]]; then
  INPUTS+=( -i "$MEDIA/music.wav" )
  MUSIC_INDEX=$((N+1))
  AUDIO="[\${AUDIO_INDEX}:a]aresample=48000,volume=1.0[voice];[\${MUSIC_INDEX}:a]aresample=48000,volume=0.12[music];[voice][music]amix=inputs=2:duration=first:dropout_transition=2[aout]"
else
  AUDIO="[\${AUDIO_INDEX}:a]aresample=48000,volume=1.0[aout]"
fi

ffmpeg -hide_banner -y "\${INPUTS[@]}" -filter_complex "$FILTER;$AUDIO" \
  -map '[vout]' -map '[aout]' -shortest -c:v libx264 -preset veryfast -crf 20 \
  -pix_fmt yuv420p -c:a aac -b:a 192k -ar 48000 -movflags +faststart "$OUTPUT"

if [[ -f "$ROOT/captions.srt" ]]; then
  TEMP="$OUTPUT.captioned.mp4"
  ffmpeg -hide_banner -y -i "$OUTPUT" \
    -vf "subtitles=$ROOT/captions.srt:force_style='$CAPTION_STYLE'" \
    -c:v libx264 -preset veryfast -crf 20 -c:a copy -movflags +faststart "$TEMP"
  mv "$TEMP" "$OUTPUT"
fi

DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$OUTPUT")
DIMENSIONS=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$OUTPUT")
[[ "$DIMENSIONS" == "$WIDTH"x"$HEIGHT" ]] || { echo "Unexpected dimensions: $DIMENSIONS" >&2; exit 1; }
python3 - "$DURATION" <<'PY'
import sys
d=float(sys.argv[1])
if d <= 1 or d > 900: raise SystemExit(f"Duration outside allowed range: {d}")
PY
sha256sum "$OUTPUT" | tee "$OUTPUT.sha256"
printf 'Rendered: %s\nFormat: %s\nDimensions: %s\nDuration: %s\n' "$OUTPUT" "$RATIO" "$DIMENSIONS" "$DURATION"
