#!/usr/bin/env python3
"""Regression tests for overlapping word-aligned subtitle cues."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from align_voiceover_captions import normalize_overlapping_groups


def word(text, start, end):
    return {"text": text, "start": float(start), "end": float(end)}


class CaptionGroupingTests(unittest.TestCase):
    def test_short_overlapping_sentence_boundary_is_merged(self):
        groups = [
            [word("él.", 23.76, 23.94)],
            [
                word("¿Qué", 24.00, 24.18),
                word("versión", 24.18, 24.52),
                word("elegirías?", 24.52, 25.169),
            ],
        ]
        # Raw ASR timestamps do not overlap, but the 250 ms SRT minimum would.
        result = normalize_overlapping_groups(groups)
        self.assertEqual(len(result), 1)
        self.assertEqual(
            " ".join(item["text"] for item in result[0]),
            "él. ¿Qué versión elegirías?",
        )

    def test_long_overlapping_groups_are_separated(self):
        first = [word(f"palabra{i}", i * 0.2, i * 0.2 + 0.3) for i in range(6)]
        first[-1]["start"] = 1.0
        first[-1]["end"] = 1.7
        second = [word(f"siguiente{i}", 1.65 + i * 0.2, 1.85 + i * 0.2) for i in range(6)]
        result = normalize_overlapping_groups([first, second])
        self.assertEqual(len(result), 2)
        self.assertLessEqual(result[0][-1]["end"], result[1][0]["start"])

    def test_non_overlapping_groups_are_unchanged(self):
        groups = [
            [word("hola", 0.0, 0.3)],
            [word("mundo", 0.5, 0.8)],
        ]
        result = normalize_overlapping_groups(groups)
        self.assertEqual(result, groups)


if __name__ == "__main__":
    unittest.main(verbosity=2)
