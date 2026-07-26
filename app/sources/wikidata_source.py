"""
Tagicus - Source: Wikidata

CC0 licensed, Wikimedia Foundation. Fully open data.
Used as a verification layer — confirms artist/album/year facts
rather than primary identification.
"""

import urllib.request
import urllib.parse
import json
from models import SourceResult


SEARCH_URL = "https://www.wikidata.org/w/api.php"
SPARQL_URL = "https://query.wikidata.org/sparql"


def lookup_wikidata(artist=None, title=None, album=None, year=None):
    """Verify music metadata against Wikidata.

    Uses SPARQL to check if the artist/song/album combination
    exists in Wikidata's knowledge graph.
    """

    if not artist:
        return SourceResult(source="wikidata", confidence=0.0, raw={"note": "needs artist name"})

    # First, find the artist entity
    artist_id = _find_entity(artist, "Q5,Q215380,Q4438121")  # person, band, duo

    if not artist_id:
        return SourceResult(source="wikidata", confidence=0.0,
                            raw={"note": f"artist '{artist}' not found in Wikidata"})

    # Query for songs/albums by this artist
    found_album = None
    found_year = None
    found_genre = None

    if title:
        song_data = _find_song_by_artist(artist_id, title)
        if song_data:
            found_album = song_data.get("album")
            found_year = song_data.get("year")
            found_genre = song_data.get("genre")

    # If no song found, try album directly
    if not found_album and album:
        album_data = _find_album_by_artist(artist_id, album)
        if album_data:
            found_album = album_data.get("album")
            found_year = album_data.get("year")
            found_genre = album_data.get("genre")

    # Get artist genre if we don't have one yet
    if not found_genre:
        found_genre = _get_artist_genre(artist_id)

    confidence = 0.5  # Verification source, not primary
    if found_album and found_year:
        confidence = 0.6

    return SourceResult(
        source="wikidata",
        artist=artist,  # We searched by artist, so echo it back
        title=title,
        album=found_album,
        year=found_year,
        genre=found_genre,
        confidence=confidence,
        raw={"artist_entity": artist_id}
    )


def _find_entity(name, instance_types=""):
    """Search Wikidata for an entity by name."""

    params = urllib.parse.urlencode({
        "action": "wbsearchentities",
        "search": name,
        "language": "en",
        "format": "json",
        "limit": 5,
        "type": "item",
    })
    url = f"{SEARCH_URL}?{params}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Tagicus/0.1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        results = data.get("search", [])
        if results:
            return results[0].get("id")
    except Exception:
        pass

    return None


def _find_song_by_artist(artist_id, title):
    """SPARQL query to find a song by an artist."""

    # Escape quotes in title
    safe_title = title.replace('"', '\\"').replace("'", "\\'")

    query = f"""
    SELECT ?songLabel ?albumLabel ?year ?genreLabel WHERE {{
      ?song wdt:P175 wd:{artist_id} .
      ?song rdfs:label ?songLabel .
      FILTER(LANG(?songLabel) = "en")
      FILTER(CONTAINS(LCASE(?songLabel), LCASE("{safe_title}")))
      OPTIONAL {{ ?song wdt:P361 ?album . ?album rdfs:label ?albumLabel . FILTER(LANG(?albumLabel) = "en") }}
      OPTIONAL {{ ?song wdt:P577 ?date . BIND(YEAR(?date) AS ?year) }}
      OPTIONAL {{ ?song wdt:P136 ?genre . ?genre rdfs:label ?genreLabel . FILTER(LANG(?genreLabel) = "en") }}
    }} LIMIT 1
    """

    return _run_sparql(query)


def _find_album_by_artist(artist_id, album_name):
    """SPARQL query to find an album by an artist."""

    safe_album = album_name.replace('"', '\\"').replace("'", "\\'")

    query = f"""
    SELECT ?albumLabel ?year ?genreLabel WHERE {{
      ?album wdt:P175 wd:{artist_id} .
      ?album wdt:P31/wdt:P279* wd:Q482994 .
      ?album rdfs:label ?albumLabel .
      FILTER(LANG(?albumLabel) = "en")
      FILTER(CONTAINS(LCASE(?albumLabel), LCASE("{safe_album}")))
      OPTIONAL {{ ?album wdt:P577 ?date . BIND(YEAR(?date) AS ?year) }}
      OPTIONAL {{ ?album wdt:P136 ?genre . ?genre rdfs:label ?genreLabel . FILTER(LANG(?genreLabel) = "en") }}
    }} LIMIT 1
    """

    result = _run_sparql(query)
    if result:
        result["album"] = result.pop("albumLabel", None)
    return result


def _get_artist_genre(artist_id):
    """Get the primary genre for an artist from Wikidata."""

    query = f"""
    SELECT ?genreLabel WHERE {{
      wd:{artist_id} wdt:P136 ?genre .
      ?genre rdfs:label ?genreLabel .
      FILTER(LANG(?genreLabel) = "en")
    }} LIMIT 1
    """

    result = _run_sparql(query)
    if result:
        return result.get("genre") or result.get("genreLabel")
    return None


def _run_sparql(query):
    """Execute a SPARQL query against Wikidata."""

    params = urllib.parse.urlencode({
        "query": query,
        "format": "json",
    })
    url = f"{SPARQL_URL}?{params}"

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Tagicus/0.1.0",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())

        bindings = data.get("results", {}).get("bindings", [])
        if not bindings:
            return None

        result = {}
        for key, val in bindings[0].items():
            result[key] = val.get("value")

        return result
    except Exception:
        return None
