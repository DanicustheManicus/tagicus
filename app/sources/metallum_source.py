"""
Tagicus - Source: Encyclopaedia Metallum (Metal Archives)

The most comprehensive metal music database.
Uses the search API at metal-archives.com.
No key required.
Privacy: Semi — community site with basic analytics.
"""

import urllib.request
import urllib.parse
import json
from models import SourceResult


SEARCH_URL = "https://www.metal-archives.com/search/ajax-advanced/searching/songs"


def lookup_metallum(artist=None, title=None):
    if not title:
        return SourceResult(source="metallum", confidence=0.0, raw={"note": "needs title"})

    params = {
        "songTitle": title,
        "bandName": artist or "",
        "sEcho": "1",
        "iDisplayStart": "0",
        "iDisplayLength": "5",
    }

    try:
        url = f"{SEARCH_URL}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Tagicus/0.1.0",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        return SourceResult(source="metallum", confidence=0.0, raw={"error": f"Metallum error: {e}"})

    entries = data.get("aaData", [])
    if not entries:
        return SourceResult(source="metallum", confidence=0.0, raw={"note": "no results found"})

    # Each entry is an array: [band_link, album_link, song_type, song_title, ...]
    entry = entries[0]

    found_artist = None
    found_album = None
    found_title = None
    found_genre = "Metal"

    # Parse band name from HTML link
    if len(entry) > 0:
        import re
        band_match = re.search(r'>([^<]+)<', str(entry[0]))
        if band_match:
            found_artist = band_match.group(1).strip()

    # Parse album name from HTML link
    if len(entry) > 1:
        import re
        album_match = re.search(r'>([^<]+)<', str(entry[1]))
        if album_match:
            found_album = album_match.group(1).strip()

    # Song title
    if len(entry) > 3:
        found_title = str(entry[3]).strip()

    # Get year from album page if we can extract the link
    found_year = None
    if len(entry) > 1:
        import re
        link_match = re.search(r'href="([^"]+)"', str(entry[1]))
        if link_match:
            try:
                album_url = link_match.group(1)
                req2 = urllib.request.Request(album_url, headers={
                    "User-Agent": "Tagicus/0.1.0",
                })
                with urllib.request.urlopen(req2, timeout=5) as resp2:
                    html = resp2.read().decode(errors="ignore")
                    year_match = re.search(r'class="album_info".*?(\d{4})', html, re.DOTALL)
                    if not year_match:
                        year_match = re.search(r'>(\d{4})<', html)
                    if year_match:
                        found_year = year_match.group(1)
            except Exception:
                pass

    confidence = 0.6
    if found_artist and found_title and found_album:
        confidence = 0.7

    return SourceResult(
        source="metallum",
        artist=found_artist,
        title=found_title,
        album=found_album,
        year=found_year,
        genre=found_genre,
        confidence=confidence,
        raw={}
    )
