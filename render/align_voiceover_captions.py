#!/usr/bin/env python3
"""Align the approved Spanish script to word timestamps from Vosk ASR."""
from __future__ import annotations
import argparse
import difflib
import json
import re
import wave
from pathlib import Path

def normalize_token(text: str) -> str:
    return "".join(re.findall(r"[a-z0-9áéíóúüñ]", text.lower()))

def srt_time(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def normalize_overlapping_groups(groups):
    """Merge short adjacent caption groups whose ASR timings overlap."""
    normalized = []
    for group in groups:
        current = [dict(word) for word in group]
        if not current:
            continue
        if normalized:
            previous = normalized[-1]
            # The SRT writer below enforces a 250 ms minimum cue duration.
            # Compare against that effective display end, not only ASR word end.
            previous_cue_end = max(previous[0]["start"] + 0.25, previous[-1]["end"])
            if current[0]["start"] < previous_cue_end:
                combined = previous + current
                combined_text = " ".join(word["text"] for word in combined).strip()
                if len(combined) <= 6 and len(combined_text) <= 42:
                    previous.extend(current)
                    continue
                safe_end = current[0]["start"] - 0.04
                minimum_end = max(previous[0]["start"] + 0.25, previous[-1]["start"] + 0.08)
                if safe_end >= minimum_end:
                    previous[-1]["end"] = safe_end
                else:
                    shift = previous_cue_end + 0.04 - current[0]["start"]
                    for word in current:
                        word["start"] += shift
                        word["end"] += shift
        normalized.append(current)
    return normalized

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", required=True)
    parser.add_argument("--expected-text", required=True)
    parser.add_argument("--captions", required=True)
    parser.add_argument("--model", required=True)
    args = parser.parse_args()

    from vosk import Model, KaldiRecognizer

    expected = Path(args.expected_text).read_text(encoding="utf-8").strip()
    expected_tokens = re.findall(r"\S+", expected)
    expected_norm = [normalize_token(token) for token in expected_tokens]
    expected_norm = [token for token in expected_norm if token]

    with wave.open(args.audio, "rb") as audio:
        if audio.getnchannels() != 1 or audio.getsampwidth() != 2 or audio.getframerate() != 16000:
            raise SystemExit("Vosk input must be 16 kHz, mono, 16-bit PCM WAV.")
        recognizer = KaldiRecognizer(Model(args.model), audio.getframerate())
        recognizer.SetWords(True)
        recognized = []
        while True:
            data = audio.readframes(4000)
            if not data:
                break
            if recognizer.AcceptWaveform(data):
                recognized.extend(json.loads(recognizer.Result()).get("result", []))
        recognized.extend(json.loads(recognizer.FinalResult()).get("result", []))
        duration = audio.getnframes() / audio.getframerate()

    recognized = [
        {"text": item.get("word", ""), "start": float(item.get("start", 0)), "end": float(item.get("end", 0))}
        for item in recognized if item.get("word")
    ]
    actual_norm = [normalize_token(item["text"]) for item in recognized]
    actual_norm = [token for token in actual_norm if token]
    if not actual_norm:
        raise SystemExit("Vosk did not return word-level timestamps.")

    similarity = difflib.SequenceMatcher(a=expected_norm, b=actual_norm).ratio()
    if similarity < 0.78:
        raise SystemExit(f"Voice transcript differs too much from approved script (similarity={similarity:.3f}); captions were not generated.")

    matcher = difflib.SequenceMatcher(a=expected_norm, b=actual_norm)
    timing = [None] * len(expected_norm)
    for block in matcher.get_matching_blocks():
        for offset in range(block.size):
            timing[block.a + offset] = recognized[block.b + offset]

    known = [i for i, value in enumerate(timing) if value is not None]
    if not known:
        raise SystemExit("Could not align approved script words to the voiceover.")

    for i, value in enumerate(timing):
        if value is not None:
            continue
        previous = max((j for j in known if j < i), default=None)
        following = min((j for j in known if j > i), default=None)
        left = timing[previous]["end"] if previous is not None else 0.0
        right = timing[following]["start"] if following is not None else duration
        gap_count = (following - previous - 1) if previous is not None and following is not None else (
            following if previous is None else len(timing) - previous - 1
        )
        position = i - previous if previous is not None else i + 1
        step = max(0.08, (right - left) / max(1, gap_count + 1))
        start = left + step * (position - 1)
        timing[i] = {"start": start, "end": min(right, start + max(0.12, step * 0.82))}

    timed_words = [
        {"text": token, "start": float(timing[i]["start"]), "end": float(timing[i]["end"])}
        for i, token in enumerate(expected_tokens) if normalize_token(token)
    ]

    groups = []
    current = []
    for word in timed_words:
        candidate = current + [word]
        candidate_text = " ".join(item["text"] for item in candidate).strip()
        pause = word["start"] - current[-1]["end"] if current else 0
        sentence_end = bool(re.search(r"[.!?…][\"'”’)]?$", current[-1]["text"])) if current else False
        if current and (len(candidate) > 6 or len(candidate_text) > 42 or pause > 0.48 or sentence_end):
            groups.append(current)
            current = [word]
        else:
            current = candidate
    if current:
        groups.append(current)

    groups = normalize_overlapping_groups(groups)

    output = []
    for index, group in enumerate(groups, 1):
        start = max(0.0, group[0]["start"])
        end = max(start + 0.25, group[-1]["end"])
        text = " ".join(item["text"] for item in group).strip()
        output.append(f"{index}\n{srt_time(start)} --> {srt_time(end)}\n{text}\n")
    Path(args.captions).parent.mkdir(parents=True, exist_ok=True)
    Path(args.captions).write_text("\n".join(output), encoding="utf-8")
    print(f"Created {len(groups)} caption cues; transcript similarity={similarity:.3f}; source duration={duration:.2f}s.")

if __name__ == "__main__":
    main()
