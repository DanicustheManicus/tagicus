"""
Tagicus - Source: VocaDB

Database for Vocaloid, anime, and Japanese music.
Free API, no key required.
Privacy: Full — community site, no tracking.
"""

import urllib.request
import urllib.parse
import json
from models import SourceResult


API_URL = "https://vocadb.net/api"


def lookup_vocadb(artist=None, title=None):
    if not title:
        return SourceResult(source="vocadb", confidence=0.0, raw={"note": "needs title"})

    query = f"{artist} {title}" if artist else title

    try:
        params = urllib.parse.urlencode({
            "query": query,
            "maxResults": 5,
            "nameMatchMode": "Auto",
            "fields": "Artists,Names",
            "songTypes": "",
        })
        url = f"{API_URL}/songs?{params}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Tagicus/0.1.0",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        return SourceResult(source="vocadb", confidence=0.0, raw={"error": f"VocaDB error: {e}"})

    items = data.get("items", [])
    if not items:
        return SourceResult(source="vocadb", confidence=0.0, raw={"note": "no results found"})

    song = items[0]

    found_title = song.get("defaultName") or song.get("name")
    found_artist = None
    found_year = None
    found_genre = None

    # Get artist from the artist string
    artist_string = song.get("artistString")
    if artist_string:
        found_artist = artist_string.split(" feat.")[0].strip()

    # Get year from publish date
    publish_date = song.get("publishDate")
    if publish_date and len(publish_date) >= 4:
        found_year = publish_date[:4]

    # Song type as genre hint
    song_type = song.get("songType")
    if song_type:
        type_map = {
            "Original": "Vocaloid",
            "Cover": "Cover",
            "Remix": "Remix",
            "MusicPV": "Vocaloid",
        }
        found_genre = type_map.get(song_type, song_type)

    # Try to get album info
    found_album = None
    song_id = song.get("id")
    if song_id:
        try:
            album_url = f"{API_URL}/songs/{song_id}?fields=Albums"
            req2 = urllib.request.Request(album_url, headers={
                "User-Agent": "Tagicus/0.1.0",
                "Accept": "application/json",
            })
            with urllib.request.urlopen(req2, timeout=5) as resp2:
                detail = json.loads(resp2.read().decode())

            albums = detail.get("albums", [])
            if albums:
                found_album = albums[0].get("name") or albums[0].get("defaultName")
        except Exception:
            pass

    confidence = 0.55
    if found_artist and found_title:
        confidence = 0.65

    return SourceResult(
        source="vocadb",
        artist=found_artist,
        title=found_title,
        album=found_album,
        year=found_year,
        genre=found_genre,
        confidence=confidence,
        raw={"vocadb_id": song_id}
    )
