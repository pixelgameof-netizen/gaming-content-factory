#!/usr/bin/env python3
"""Regression test: SRT captions must render in the lower safe area, not off-frame.

FFmpeg/libass converts SRT to ASS using a 384x288 script canvas. The renderer
must express force_style dimensions in that coordinate system for each output
size. This smoke test checks both vertical and horizontal presets using FFmpeg.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


PRESETS = {
    "vertical": {
        "width": 1080,
        "height": 1920,
        "style": (
            "FontName=DejaVu Sans,FontSize=10,Bold=1,"
            "PrimaryColour=&H00FFFFFF,OutlineColour=&HCC000000,"
            "BorderStyle=1,Outline=1,Shadow=1,Alignment=2,"
            "MarginL=30,MarginR=30,MarginV=40"
        ),
    },
    "horizontal": {
        "width": 1920,
        "height": 1080,
        "style": (
            "FontName=DejaVu Sans,FontSize=13,Bold=1,"
            "PrimaryColour=&H00FFFFFF,OutlineColour=&HCC000000,"
            "BorderStyle=1,Outline=1,Shadow=1,Alignment=2,"
            "MarginL=24,MarginR=24,MarginV=22"
        ),
    },
}


def render_test_frame(width: int, height: int, style: str, srt: Path) -> bytes:
    vf = f"subtitles={srt}:force_style='{style}',select='eq(n,1)'"
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", f"color=c=blue:s={width}x{height}:d=2:r=2",
        "-vf", vf, "-frames:v", "1", "-f", "rawvideo",
        "-pix_fmt", "rgb24", "pipe:1",
    ]
    completed = subprocess.run(command, check=True, capture_output=True)
    return completed.stdout


def bright_pixel_rows(frame: bytes, width: int, height: int) -> list[int]:
    row_bytes = width * 3
    expected = row_bytes * height
    if len(frame) != expected:
        raise RuntimeError(f"Expected {expected} raw bytes, got {len(frame)}")
    rows: list[int] = []
    for y in range(height):
        row = frame[y * row_bytes:(y + 1) * row_bytes]
        bright = 0
        for x in range(0, row_bytes, 3):
            if row[x] > 220 and row[x + 1] > 220 and row[x + 2] > 220:
                bright += 1
        if bright >= 6:
            rows.append(y)
    return rows


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="gcf-caption-test-") as tmp:
        srt = Path(tmp) / "caption.srt"
        srt.write_text(
            "1\n00:00:00,000 --> 00:00:02,000\nCAPTION TEST\n",
            encoding="utf-8",
        )
        for name, preset in PRESETS.items():
            width, height = preset["width"], preset["height"]
            frame = render_test_frame(width, height, preset["style"], srt)
            rows = bright_pixel_rows(frame, width, height)
            lower_band = [y for y in rows if int(height * 0.72) <= y <= int(height * 0.96)]
            upper_band = [y for y in rows if y < int(height * 0.20)]
            if not lower_band:
                raise SystemExit(f"{name}: no caption pixels found in the lower safe area")
            if upper_band:
                raise SystemExit(f"{name}: caption leaked into the top edge (rows {upper_band[:5]})")
            print(f"{name}: subtitle safe-area check passed ({min(lower_band)}-{max(lower_band)}px)")


if __name__ == "__main__":
    main()
