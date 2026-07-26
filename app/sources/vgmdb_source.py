"""
Tagicus - Source: VGMdb

Community database for video game, anime, and film soundtracks.
Uses the unofficial API at vgmdb.info.
No key required, no authentication.
Privacy: Full — community site, no tracking.
"""

import urllib.request
import urllib.parse
import json
from models import SourceResult


SEARCH_URL = "https://vgmdb.info/search"


def lookup_vgmdb(artist=None, title=None, album=None):
    query = " ".join(filter(None, [artist, title, album]))
    if not query:
        return SourceResult(source="vgmdb", confidence=0.0, raw={"note": "no search criteria"})

    try:
        params = urllib.parse.urlencode({"q": query, "format": "json"})
        url = f"{SEARCH_URL}?{params}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Tagicus/0.1.0",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        return SourceResult(source="vgmdb", confidence=0.0, raw={"error": f"VGMdb error: {e}"})

    # Check album results
    albums = data.get("results", {}).get("albums", [])
    if not albums:
        return SourceResult(source="vgmdb", confidence=0.0, raw={"note": "no results found"})

    album_result = albums[0]
    found_album = album_result.get("titles", {}).get("en") or album_result.get("titles", {}).get("ja")

    # Try to get more details from the album page
    found_artist = None
    found_year = None
    found_genre = "Soundtrack"

    link = album_result.get("link")
    if link:
        try:
            detail_url = f"https://vgmdb.info/{link}?format=json"
            req2 = urllib.request.Request(detail_url, headers={
                "User-Agent": "Tagicus/0.1.0",
                "Accept": "application/json",
            })
            with urllib.request.urlopen(req2, timeout=5) as resp2:
                detail = json.loads(resp2.read().decode())

            # Get composers/performers
            performers = detail.get("performers", [])
            composers = detail.get("composers", [])
            if composers:
                names = composers[0].get("names", {})
                found_artist = names.get("en") or names.get("ja")
            elif performers:
                names = performers[0].get("names", {})
                found_artist = names.get("en") or names.get("ja")

            # Get year from release date
            release_date = detail.get("release_date")
            if release_date and len(release_date) >= 4:
                found_year = release_date[:4]

            # Get category as genre hint
            category = detail.get("category")
            if category:
                found_genre = category

        except Exception:
            pass

    confidence = 0.55
    if found_artist and found_album:
        confidence = 0.65

    return SourceResult(
        source="vgmdb",
        artist=found_artist or artist,
        title=title,
        album=found_album,
        year=found_year,
        genre=found_genre,
        confidence=confidence,
        raw={"link": link}
    )
