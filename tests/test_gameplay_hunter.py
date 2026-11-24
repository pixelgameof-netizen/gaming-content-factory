import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.gameplay_hunter.discover_commons import (
    license_key, clean, discover, parse_games, is_commons_media_url, is_trusted_license_url,
    is_relevant_game, load_game_profiles, search_terms_for_game
)


class HunterTests(unittest.TestCase):
    # Keep parsing behavior covered for comma, semicolon, and real newline separators.
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
        self.assertTrue(is_trusted_license_url("https://creativecommons.org/licenses/by/4.0/", "CC BY 4.0"))
        self.assertTrue(is_trusted_license_url("https://creativecommons.org/licenses/by/3.0/", "CC BY 3.0"))
        self.assertTrue(is_trusted_license_url("https://creativecommons.org/publicdomain/zero/1.0/", "CC0"))
        self.assertFalse(is_trusted_license_url("https://commons.wikimedia.org/wiki/File:Example", "CC BY 4.0"))
        self.assertFalse(is_trusted_license_url("https://creativecommons.org/licenses/by/3.0/", "CC BY 4.0"))
        self.assertFalse(is_trusted_license_url("http://creativecommons.org/licenses/by/4.0/", "CC BY 4.0"))
        self.assertFalse(is_trusted_license_url("https://creativecommons.org.evil.example/license", "CC BY 4.0"))

    def test_game_parser_splits_deduplicates_and_caps(self):
        games = parse_games("Minecraft; Fortnite\nROBLOX, minecraft, Zelda, Valorant, Apex, Call of Duty")
        self.assertEqual(games, ["Minecraft", "Fortnite", "ROBLOX", "Zelda", "Valorant", "Apex"])

    def test_game_profiles_load_aliases_and_keep_custom_games(self):
        defaults, profiles = load_game_profiles()
        self.assertEqual(len(defaults), 6)
        self.assertIn("minecraft", profiles)
        self.assertIn("GTA V", search_terms_for_game("Grand Theft Auto", profiles))
        self.assertEqual(search_terms_for_game("A game not in config", profiles), ["A game not in config"])

    def test_loaded_profile_aliases_are_bounded_and_deduplicated(self):
        _, profiles = load_game_profiles()
        for terms in profiles.values():
            self.assertLessEqual(len(terms), 5)
            self.assertEqual(len(terms), len(set(terms)))
            self.assertTrue(all(term.strip() for term in terms))

    def test_clean(self):
        self.assertEqual(clean("  Minecraft  gameplay\n clip "), "Minecraft gameplay clip")

    def test_relevance_filter_rejects_unrelated_games(self):
        self.assertTrue(is_relevant_game("Minecraft", "File:Minecraft Classic Gameplay.webm", ""))
        self.assertTrue(is_relevant_game("Minecraft", "File:Gameplay.webm", "Gameplay footage of Minecraft."))
        self.assertFalse(is_relevant_game("Minecraft", "File:Dishonored 2 gameplay clip.webm", "A montage from Dishonored 2."))
        self.assertFalse(is_relevant_game("Minecraft", "File:Luanti 5.10.webm", "Luanti is an alternative to Minecraft."))
        self.assertFalse(is_relevant_game("Minecraft", "File:Luanti Gameplay.webm", "Gameplay of Luanti, an alternative to Minecraft."))
        self.assertTrue(is_relevant_game("Minecraft", "File:Gameplay.webm", "Minecraft gameplay footage."))

    def test_discover_empty_game_list(self):
        result = discover([])
        self.assertEqual(result["candidate_count"], 0)
        self.assertTrue(result["policy"]["no_download"])
        self.assertTrue(result["policy"]["no_auto_approval"])


if __name__ == "__main__":
    unittest.main()
