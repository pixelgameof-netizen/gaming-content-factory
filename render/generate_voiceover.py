#!/usr/bin/env python3
"""Generate Spanish narration and sentence-synchronised SRT with Kokoro ONNX."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro
from misaki.espeak import EspeakG2P

SAMPLE_RATE = 24000
VOICE = "ef_dora"
MAX_TEXT_CHARS = 8000


def split_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[.!?])\s+", normalized)
    return [part.strip() for part in sentences if part.strip()]


def srt_time(seconds: float) -> str:
    millis = max(0, round(seconds * 1000))
    hours, remainder = divmod(millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, ms = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{ms:03}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--voices", required=True, type=Path)
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--captions", required=True, type=Path)
    args = parser.parse_args()

    text = args.script.read_text(encoding="utf-8").strip()
    if not text or len(text) > MAX_TEXT_CHARS:
        raise SystemExit(f"Narration text must contain 1–{MAX_TEXT_CHARS} characters")
    if not args.model.is_file() or not args.voices.is_file():
        raise SystemExit("Pinned Kokoro model assets are missing")

    sentences = split_sentences(text)
    if not sentences:
        raise SystemExit("No speakable sentences found")

    g2p = EspeakG2P(language="es")
    engine = Kokoro(str(args.model), str(args.voices))
    clips: list[np.ndarray] = []
    cues: list[tuple[float, float, str]] = []
    cursor = 0.0
    pause = np.zeros(int(0.22 * SAMPLE_RATE), dtype=np.float32)

    try:
        for sentence in sentences:
            phonemes, _ = g2p(sentence)
            if not phonemes.strip():
                continue
            samples, rate = engine.create(phonemes, VOICE, speed=1.02, is_phonemes=True)
            if rate != SAMPLE_RATE:
                raise SystemExit(f"Unexpected TTS sample rate: {rate}")
            samples = np.asarray(samples, dtype=np.float32).reshape(-1)
            if samples.size == 0:
                raise SystemExit("Kokoro returned an empty narration segment")
            start = cursor
            clips.append(samples)
            cursor += samples.size / SAMPLE_RATE
            cues.append((start, cursor, sentence))
            clips.append(pause)
            cursor += pause.size / SAMPLE_RATE
    finally:
        engine.voices.close()

    if not cues or cursor <= 1:
        raise SystemExit("Narration generation did not produce usable audio")
    audio = np.concatenate(clips)
    args.audio.parent.mkdir(parents=True, exist_ok=True)
    args.captions.parent.mkdir(parents=True, exist_ok=True)
    sf.write(args.audio, audio, SAMPLE_RATE, subtype="PCM_16")

    lines: list[str] = []
    for index, (start, end, sentence) in enumerate(cues, 1):
        lines.extend([str(index), f"{srt_time(start)} --> {srt_time(end)}", sentence, ""])
    args.captions.write_text("\n".join(lines), encoding="utf-8")
    print(f"Generated Spanish voiceover ({cursor:.1f}s) and {len(cues)} timed subtitle cues.")


if __name__ == "__main__":
    main()
