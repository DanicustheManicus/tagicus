"""
Tagicus - Source: LRCLIB

Free, open lyrics database. No API key, no authentication.
Supports both plain text and synced (timestamped) lyrics.
Privacy: Full — no tracking, no accounts.
"""

import urllib.request
import urllib.parse
import json


SEARCH_URL = "https://lrclib.net/api/search"
GET_URL = "https://lrclib.net/api/get"


def fetch_lyrics(artist=None, title=None, album=None, duration=None):
    """Search LRCLIB for lyrics by artist and title.
    
    Returns dict with:
        plain: plain text lyrics (or None)
        synced: timestamped LRC lyrics (or None)
        found: True/False
    """

    if not artist or not title:
        return {"found": False, "plain": None, "synced": None, "error": "needs artist and title"}

    # Try exact match first
    params = {
        "artist_name": artist,
        "track_name": title,
    }
    if album:
        params["album_name"] = album
    if duration:
        params["duration"] = str(int(duration))

    try:
        url = f"{GET_URL}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Tagicus/0.1.0",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())

        plain = data.get("plainLyrics")
        synced = data.get("syncedLyrics")

        if plain or synced:
            return {
                "found": True,
                "plain": plain,
                "synced": synced,
                "source_id": data.get("id"),
            }
    except Exception:
        pass

    # Fall back to search
    try:
        search_query = f"{artist} {title}"
        search_params = urllib.parse.urlencode({"q": search_query})
        url = f"{SEARCH_URL}?{search_params}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Tagicus/0.1.0",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=5) as resp:
            results = json.loads(resp.read().decode())

        if results and len(results) > 0:
            best = results[0]
            plain = best.get("plainLyrics")
            synced = best.get("syncedLyrics")

            if plain or synced:
                return {
                    "found": True,
                    "plain": plain,
                    "synced": synced,
                    "source_id": best.get("id"),
                    "matched_artist": best.get("artistName"),
                    "matched_title": best.get("trackName"),
                }
    except Exception as e:
        return {"found": False, "plain": None, "synced": None, "error": str(e)}

    return {"found": False, "plain": None, "synced": None}
