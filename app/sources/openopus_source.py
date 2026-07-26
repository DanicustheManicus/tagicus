"""
Tagicus - Source: Open Opus

Free API for classical music metadata.
No key required, no authentication.
Covers composers, works, and recordings.
Privacy: Full — open source, no tracking.
"""

import urllib.request
import urllib.parse
import json
from models import SourceResult


BASE_URL = "https://api.openopus.org"


def lookup_openopus(artist=None, title=None):
    if not artist:
        return SourceResult(source="openopus", confidence=0.0, raw={"note": "needs artist name"})

    # First find the composer
    try:
        search_url = f"{BASE_URL}/composer/list/search/{urllib.parse.quote(artist)}.json"
        req = urllib.request.Request(search_url, headers={"User-Agent": "Tagicus/0.1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        return SourceResult(source="openopus", confidence=0.0, raw={"error": f"Open Opus error: {e}"})

    composers = data.get("composers", [])
    if not composers or data.get("status", {}).get("success") == "false":
        return SourceResult(source="openopus", confidence=0.0, raw={"note": "composer not found"})

    composer = composers[0]
    found_artist = composer.get("complete_name") or composer.get("name")
    composer_id = composer.get("id")
    found_genre = "Classical"

    # Search for the work if we have a title
    found_title = None
    found_album = None
    if title and composer_id:
        try:
            work_url = f"{BASE_URL}/work/list/composer/{composer_id}/genre/all/search/{urllib.parse.quote(title)}.json"
            req2 = urllib.request.Request(work_url, headers={"User-Agent": "Tagicus/0.1.0"})
            with urllib.request.urlopen(req2, timeout=5) as resp2:
                work_data = json.loads(resp2.read().decode())

            works = work_data.get("works", [])
            if works and work_data.get("status", {}).get("success") != "false":
                work = works[0]
                found_title = work.get("title")
                found_album = work.get("subtitle") or found_title
        except Exception:
            pass

    confidence = 0.6 if found_title else 0.4

    return SourceResult(
        source="openopus",
        artist=found_artist,
        title=found_title or title,
        album=found_album,
        genre=found_genre,
        confidence=confidence,
        raw={"composer_id": composer_id}
    )
