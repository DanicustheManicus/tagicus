"""
Tagicus - Source: Deezer

Free search API, no key required, no authentication.
90+ million tracks. GDPR-compliant (French company).
"""

import urllib.request
import urllib.parse
import json
from models import SourceResult


SEARCH_URL = "https://api.deezer.com/search"


def lookup_deezer(artist=None, title=None):
    """Search Deezer for a track by artist and/or title."""

    if not artist and not title:
        return SourceResult(source="deezer", confidence=0.0, raw={"note": "no search criteria"})

    # Build query
    parts = []
    if artist:
        parts.append(f'artist:"{artist}"')
    if title:
        parts.append(f'track:"{title}"')
    query = " ".join(parts)

    params = urllib.parse.urlencode({"q": query, "limit": 5})
    url = f"{SEARCH_URL}?{params}"

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Tagicus/0.1.0",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        return SourceResult(source="deezer", confidence=0.0, raw={"error": f"Deezer API error: {e}"})

    tracks = data.get("data", [])
    if not tracks:
        return SourceResult(source="deezer", confidence=0.0, raw={"note": "no results found", "query": query})

    # Take the best match
    track = tracks[0]

    found_artist = track.get("artist", {}).get("name")
    found_title = track.get("title")
    found_album = track.get("album", {}).get("title")

    # Deezer doesn't return year or track number in search results
    # but we can get it from the album endpoint
    found_year = None
    found_track = track.get("track_position")
    found_genre = None

    album_id = track.get("album", {}).get("id")
    if album_id:
        try:
            album_url = f"https://api.deezer.com/album/{album_id}"
            req2 = urllib.request.Request(album_url, headers={
                "User-Agent": "Tagicus/0.1.0",
                "Accept": "application/json",
            })
            with urllib.request.urlopen(req2, timeout=10) as resp2:
                album_data = json.loads(resp2.read().decode())
                release_date = album_data.get("release_date", "")
                if release_date:
                    found_year = release_date[:4]
                genres = album_data.get("genres", {}).get("data", [])
                if genres:
                    found_genre = genres[0].get("name")
        except Exception:
            pass

    # Calculate confidence based on how well the result matches the query
    confidence = 0.6
    if found_artist and artist:
        from thefuzz import fuzz
        artist_match = fuzz.ratio(found_artist.lower(), artist.lower())
        if artist_match > 90:
            confidence = 0.7
        elif artist_match < 60:
            confidence = 0.4

    return SourceResult(
        source="deezer",
        artist=found_artist,
        title=found_title,
        album=found_album,
        year=found_year,
        track=found_track,
        genre=found_genre,
        confidence=confidence,
        raw={"query": query, "deezer_id": track.get("id")}
    )
