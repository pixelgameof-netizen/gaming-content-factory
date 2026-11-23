#!/usr/bin/env python3
"""Deterministic post-render QC for Gaming Content Factory MP4 outputs."""
import argparse
import hashlib
import json
import math
import pathlib
import subprocess
import sys


def fail(message: str) -> None:
    raise SystemExit(f"QC_FAILED: {message}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=pathlib.Path)
    parser.add_argument("--aspect", choices=("9:16", "16:9"), required=True)
    parser.add_argument("--report", type=pathlib.Path, required=True)
    args = parser.parse_args()

    path = args.video
    if not path.is_file():
        fail("output file does not exist")
    size = path.stat().st_size
    if size < 1024:
        fail("output file is empty or implausibly small")

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
        check=False, capture_output=True, text=True,
    )
    if probe.returncode:
        fail("ffprobe could not read the output")
    try:
        metadata = json.loads(probe.stdout)
    except json.JSONDecodeError:
        fail("ffprobe returned invalid metadata")

    streams = metadata.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if not video:
        fail("video stream is missing")
    if not audio:
        fail("audio stream is missing")

    expected = (1080, 1920) if args.aspect == "9:16" else (1920, 1080)
    actual = (video.get("width"), video.get("height"))
    if actual != expected:
        fail(f"expected {expected[0]}x{expected[1]}, got {actual[0]}x{actual[1]}")
    if video.get("codec_name") != "h264":
        fail(f"expected H.264 video, got {video.get('codec_name')}")
    if audio.get("codec_name") != "aac":
        fail(f"expected AAC audio, got {audio.get('codec_name')}")

    try:
        duration = float((metadata.get("format") or {}).get("duration"))
        video_duration = float(video.get("duration", duration))
        audio_duration = float(audio.get("duration", duration))
    except (TypeError, ValueError):
        fail("duration metadata is missing")
    if not math.isfinite(duration) or duration <= 1 or duration > 900:
        fail(f"duration outside allowed range: {duration}")
    if abs(video_duration - audio_duration) > 1.0:
        fail("audio/video duration mismatch exceeds 1 second")

    fps_raw = video.get("avg_frame_rate", "0/1")
    try:
        numerator, denominator = fps_raw.split("/", 1)
        fps = float(numerator) / float(denominator)
    except (ValueError, ZeroDivisionError):
        fail("invalid frame-rate metadata")
    if not 23.0 <= fps <= 60.0:
        fail(f"frame rate outside 23–60 fps: {fps}")

    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    report = {
        "status": "passed",
        "file": path.name,
        "sha256": digest,
        "size_bytes": size,
        "duration_seconds": round(duration, 3),
        "aspect_ratio": args.aspect,
        "width": actual[0],
        "height": actual[1],
        "video_codec": video.get("codec_name"),
        "audio_codec": audio.get("codec_name"),
        "frame_rate": round(fps, 3),
        "checks": ["file_readable", "video_stream", "audio_stream", "dimensions",
                   "h264", "aac", "duration", "audio_video_sync", "frame_rate", "sha256"],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
