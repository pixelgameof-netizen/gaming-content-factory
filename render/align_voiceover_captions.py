#!/usr/bin/env python3
"""Create word-timed Spanish SRT captions from an approved WAV voiceover."""
from __future__ import annotations
import argparse
import difflib
import re
from pathlib import Path
from faster_whisper import WhisperModel

def normalize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9áéíóúüñ]+", text.lower())

def srt_time(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", required=True)
    parser.add_argument("--expected-text", required=True)
    parser.add_argument("--captions", required=True)
    args = parser.parse_args()

    expected = Path(args.expected_text).read_text(encoding="utf-8").strip()
    model = WhisperModel("small", device="cpu", compute_type="int8")
    segments, info = model.transcribe(
        args.audio,
        language="es",
        beam_size=5,
        word_timestamps=True,
        vad_filter=False,
        initial_prompt=expected,
    )
    words = []
    for segment in segments:
        for word in (segment.words or []):
            token = word.word.strip()
            if token:
                words.append({"text": token, "start": float(word.start), "end": float(word.end)})
    if not words:
        raise SystemExit("No word timestamps were produced for the approved voiceover.")

    actual_text = " ".join(w["text"] for w in words)
    expected_words = normalize(expected)
    actual_words = normalize(actual_text)
    similarity = difflib.SequenceMatcher(a=expected_words, b=actual_words).ratio()
    if similarity < 0.78:
        raise SystemExit(f"Voice transcript differs too much from approved script (similarity={similarity:.3f}); captions were not generated.")

    groups = []
    current = []
    for word in words:
        candidate = current + [word]
        candidate_text = " ".join(x["text"] for x in candidate).strip()
        pause = word["start"] - current[-1]["end"] if current else 0
        sentence_end = bool(re.search(r"[.!?…][\"'”’)]?$", current[-1]["text"])) if current else False
        if current and (len(candidate) > 6 or len(candidate_text) > 42 or pause > 0.48 or sentence_end):
            groups.append(current)
            current = [word]
        else:
            current = candidate
    if current:
        groups.append(current)

    output = []
    for index, group in enumerate(groups, 1):
        start = max(0.0, group[0]["start"])
        end = max(start + 0.25, group[-1]["end"])
        text = " ".join(item["text"] for item in group).strip()
        output.append(f"{index}\n{srt_time(start)} --> {srt_time(end)}\n{text}\n")
    Path(args.captions).parent.mkdir(parents=True, exist_ok=True)
    Path(args.captions).write_text("\n".join(output), encoding="utf-8")
    print(f"Created {len(groups)} caption cues; transcript similarity={similarity:.3f}; detected language={info.language}.")

if __name__ == "__main__":
    main()
