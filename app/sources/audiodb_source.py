"""
Tagicus - Source: TheAudioDB

Community-driven music metadata and artwork database.
Free API using shared key "523532" (public test key).
Good for artwork, genre, and additional metadata verification.
"""

import urllib.request
import urllib.parse
import json
from models import SourceResult


BASE_URL = "https://www.theaudiodb.com/api/v1/json/523532"


def lookup_audiodb(artist=None, title=None):
    """Search TheAudioDB for a track by artist and title."""

    if not artist or not title:
        return SourceResult(source="audiodb", confidence=0.0, raw={"note": "needs both artist and title"})

    # Search for the track
    params = urllib.parse.urlencode({"s": artist, "t": title})
    url = f"{BASE_URL}/searchtrack.php?{params}"

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Tagicus/0.1.0",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        return SourceResult(source="audiodb", confidence=0.0, raw={"error": f"AudioDB API error: {e}"})

    tracks = data.get("track")
    if not tracks:
        return SourceResult(source="audiodb", confidence=0.0, raw={"note": "no results found"})

    # Take the first match
    track = tracks[0]

    found_artist = track.get("strArtist")
    found_title = track.get("strTrack")
    found_album = track.get("strAlbum")
    found_year = None
    found_genre = track.get("strGenre")
    found_track = None

    # Get track number
    track_num = track.get("intTrackNumber")
    if track_num:
        try:
            found_track = int(track_num)
        except (ValueError, TypeError):
            pass

    # Get year from the album if available
    int_year = track.get("intYearReleased")
    if int_year:
        found_year = str(int_year)

    # Artwork URLs (stored in raw for later use)
    artwork = {
        "track_thumb": track.get("strTrackThumb"),
        "album_thumb": track.get("strAlbumThumb"),
        "artist_thumb": track.get("strArtistThumb"),
    }

    confidence = 0.65
    if found_artist and found_title and found_album:
        confidence = 0.7

    return SourceResult(
        source="audiodb",
        artist=found_artist,
        title=found_title,
        album=found_album,
        year=found_year,
        track=found_track,
        genre=found_genre,
        confidence=confidence,
        raw={
            "audiodb_track_id": track.get("idTrack"),
            "audiodb_album_id": track.get("idAlbum"),
            "artwork": artwork,
        }
    )


def get_album_art(artist=None, album=None):
    """Fetch album artwork URL from TheAudioDB."""

    if not artist or not album:
        return None

    params = urllib.parse.urlencode({"s": artist, "a": album})
    url = f"{BASE_URL}/searchalbum.php?{params}"

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Tagicus/0.1.0",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        albums = data.get("album")
        if albums:
            return albums[0].get("strAlbumThumb")
    except Exception:
        pass

    return None
