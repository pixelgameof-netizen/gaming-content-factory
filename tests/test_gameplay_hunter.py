import unittest
from tools.gameplay_hunter.discover_commons import license_key, clean, discover


class HunterTests(unittest.TestCase):
    def test_license_allowlist_is_conservative(self):
        self.assertEqual(license_key("CC BY 4.0"), "CC BY 4.0")
        self.assertEqual(license_key("CC0"), "CC0")
        self.assertIsNone(license_key("CC BY-SA 4.0"))
        self.assertIsNone(license_key("CC BY-NC 4.0"))
        self.assertIsNone(license_key(""))

    def test_clean(self):
        self.assertEqual(clean("  Minecraft  gameplay\n clip "), "Minecraft gameplay clip")

    def test_discover_empty_game_list(self):
        result = discover([])
        self.assertEqual(result["candidate_count"], 0)
        self.assertTrue(result["policy"]["no_download"])
        self.assertTrue(result["policy"]["no_auto_approval"])


if __name__ == "__main__":
    unittest.main()
