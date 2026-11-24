#!/usr/bin/env python3
"""Discover Wikimedia Commons gameplay-video candidates; never downloads or approves them."""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from typing import Any

import requests

API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "GamingContentFactory/0.1 (rights-aware gameplay discovery; contact via repository)"
ALLOWED_LICENSES = {
    "CC0": "https://creativecommons.org/publicdomain/zero/1.0/",
    "CC BY 4.0": "https://creativecommons.org/licenses/by/4.0/",
    "CC BY 3.0": "https://creativecommons.org/licenses/by/3.0/",
}
VIDEO_EXTENSIONS = (".webm", ".ogv", ".ogg", ".mp4", ".mkv", ".mov")
MAX_RESULTS_PER_GAME = 8
MAX_GAMES_PER_RUN = 6


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def is_relevant_game(game: str, title: str, description: str) -> bool:
    """Reject search spillover where another game only mentions the queried title."""
    game_text = clean(game).casefold()
    title_text = clean(title).casefold()
    description_text = clean(description).casefold()
    if not game_text:
        return False
    if game_text in title_text:
        return True
    escaped = re.escape(game_text)
    direct_gameplay = re.compile(
        rf"\b(?:gameplay(?:\s+footage)?|game)\s+(?:of\s+|:\s*)?{escaped}\b",
        re.IGNORECASE,
    )
    playing_game = re.compile(rf"\bplaying\s+{escaped}\b", re.IGNORECASE)
    return bool(direct_gameplay.search(description_text) or playing_game.search(description_text))


def parse_games(value: str) -> list[str]:
    """Parse a bounded, de-duplicated list of game names."""
    games: list[str] = []
    seen: set[str] = set()
    for part in re.split(r"[,;\n]+", value or ""):
        game = clean(part)
        key = game.casefold()
        if game and key not in seen and len(games) < MAX_GAMES_PER_RUN:
            games.append(game)
            seen.add(key)
    return games


def license_key(value: str) -> str | None:
    value = clean(value)
    if value in ALLOWED_LICENSES:
        return value
    return None


def is_commons_media_url(value: str) -> bool:
    parsed = urlparse(value or "")
    return parsed.scheme == "https" and parsed.hostname == "upload.wikimedia.org"


def is_trusted_license_url(value: str, license_name: str) -> bool:
    parsed = urlparse(value or "")
    host = (parsed.hostname or "").lower()
    expected_path = {
        "CC0": "/publicdomain/zero/1.0/",
        "CC BY 4.0": "/licenses/by/4.0/",
        "CC BY 3.0": "/licenses/by/3.0/",
    }.get(license_name)
    return (
        parsed.scheme == "https"
        and host in {"creativecommons.org", "www.creativecommons.org"}
        and parsed.path.rstrip("/") == (expected_path or "").rstrip("/")
        and not parsed.username
        and not parsed.password
    )


def search_commons(game: str, session: requests.Session, limit: int = MAX_RESULTS_PER_GAME) -> list[dict[str, Any]]:
    params = {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "generator": "search",
        "gsrnamespace": "6",
        "gsrsearch": f'"{game}" gameplay video',
        "gsrlimit": str(min(max(limit * 3, 10), 50)),
        "prop": "imageinfo",
        "iiprop": "url|mime|extmetadata",
        "iiurlwidth": "640",
    }
    response = session.get(API, params=params, timeout=(10, 30))
    response.raise_for_status()
    payload = response.json()
    pages = payload.get("query", {}).get("pages", [])
    candidates: list[dict[str, Any]] = []

    for page in pages:
        info_list = page.get("imageinfo") or []
        if not info_list:
            continue
        info = info_list[0]
        title = page.get("title", "")
        url = info.get("url", "")
        mime = info.get("mime", "")
        if not is_commons_media_url(url):
            continue
        # Require a verified video MIME type; a filename extension alone is insufficient.
        if not mime.startswith("video/"):
            continue

        meta = info.get("extmetadata") or {}
        short = meta.get("LicenseShortName", {}).get("value", "")
        license_name = license_key(short)
        # Exclude ShareAlike, NC, ND, unknown, and missing licenses.
        if not license_name:
            continue
        license_url = meta.get("LicenseUrl", {}).get("value") or ALLOWED_LICENSES[license_name]
        if not is_trusted_license_url(license_url, license_name):
            continue

        description = clean(meta.get("ImageDescription", {}).get("value", ""))
        if not is_relevant_game(game, title, description):
            continue
        artist = clean(meta.get("Artist", {}).get("value", ""))
        credit = clean(meta.get("Credit", {}).get("value", ""))
        usage = clean(meta.get("UsageTerms", {}).get("value", ""))
        source_page = "https://commons.wikimedia.org/wiki/" + requests.utils.quote(title.replace(" ", "_"), safe=":")
        candidates.append({
            "game_query": game,
            "title": title,
            "source_page": source_page,
            "direct_media_url": url,
            "thumbnail_url": info.get("thumburl"),
            "mime": mime,
            "license": license_name,
            "license_url": license_url,
            "artist": artist,
            "credit": credit,
            "usage_terms": usage,
            "description": description[:1800],
            "attribution_required": license_name != "CC0",
            "publisher_gameplay_policy_review_required": True,
            "music_rights_review_required": True,
            "rights_status": "candidate",
            "downloaded": False,
            "auto_approved": False,
        })
        if len(candidates) >= limit:
            break
    return candidates


def discover(games: list[str], session: requests.Session | None = None) -> dict[str, Any]:
    http = session or requests.Session()
    http.headers.update({"User-Agent": USER_AGENT})
    all_candidates: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    seen: set[str] = set()
    for game in games:
        game = clean(game)
        if not game:
            continue
        try:
            for item in search_commons(game, http):
                if item["source_page"] not in seen:
                    seen.add(item["source_page"])
                    all_candidates.append(item)
        except (requests.RequestException, ValueError, KeyError) as exc:
            errors.append({"game": game, "error": str(exc)[:500]})
        time.sleep(0.35)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Wikimedia Commons API",
        "candidate_count": len(all_candidates),
        "games_searched": games,
        "policy": {
            "license_allowlist": list(ALLOWED_LICENSES),
            "no_download": True,
            "no_auto_approval": True,
            "gameplay_publisher_rights_still_require_review": True,
            "third_party_music_rights_still_require_review": True,
        },
        "candidates": all_candidates,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", default="Minecraft, Fortnite, Roblox, Grand Theft Auto, Counter-Strike, Valorant")
    parser.add_argument("--output", default="artifacts/gameplay-candidates.json")
    args = parser.parse_args()
    games = parse_games(args.games)
    result = discover(games)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Discovered {result['candidate_count']} license-filtered candidates across {len(games)} game queries.")
    print(f"Saved: {output}")
    print("No files were downloaded and no rights were approved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
