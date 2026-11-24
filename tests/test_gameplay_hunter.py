import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.gameplay_hunter.discover_commons import (
    license_key, clean, discover, is_commons_media_url, is_trusted_license_url
)


class HunterTests(unittest.TestCase):
    def test_license_allowlist_is_conservative(self):
        self.assertEqual(license_key("CC BY 4.0"), "CC BY 4.0")
        self.assertEqual(license_key("CC0"), "CC0")
        self.assertEqual(license_key("CC BY 3.0"), "CC BY 3.0")
        self.assertIsNone(license_key("CC BY-SA 4.0"))
        self.assertIsNone(license_key("CC BY-NC 4.0"))
        self.assertIsNone(license_key("CC BY 4.0 with additional terms"))
        self.assertIsNone(license_key(""))

    def test_media_host_must_be_exact_https_commons_host(self):
        self.assertTrue(is_commons_media_url("https://upload.wikimedia.org/a/b/video.webm"))
        self.assertFalse(is_commons_media_url("http://upload.wikimedia.org/a/video.webm"))
        self.assertFalse(is_commons_media_url("https://upload.wikimedia.org.evil.example/video.webm"))
        self.assertFalse(is_commons_media_url("https://example.com/video.webm"))

    def test_license_url_must_use_trusted_https_host(self):
        self.assertTrue(is_trusted_license_url("https://creativecommons.org/licenses/by/4.0/"))
        self.assertTrue(is_trusted_license_url("https://commons.wikimedia.org/wiki/File:Example"))
        self.assertFalse(is_trusted_license_url("http://creativecommons.org/licenses/by/4.0/"))
        self.assertFalse(is_trusted_license_url("https://creativecommons.org.evil.example/license"))

    def test_clean(self):
        self.assertEqual(clean("  Minecraft  gameplay\n clip "), "Minecraft gameplay clip")

    def test_discover_empty_game_list(self):
        result = discover([])
        self.assertEqual(result["candidate_count"], 0)
        self.assertTrue(result["policy"]["no_download"])
        self.assertTrue(result["policy"]["no_auto_approval"])


if __name__ == "__main__":
    unittest.main()
