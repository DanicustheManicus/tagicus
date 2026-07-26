import acoustid
from models import SourceResult

def lookup_acoustid(filepath, api_key):
    try:
        results = acoustid.match(api_key, filepath, parse=False)
    except acoustid.NoBackendError:
        return SourceResult(source="acoustid", confidence=0.0, raw={"error": "fpcalc not found"})
    except acoustid.FingerprintGenerationError:
        return SourceResult(source="acoustid", confidence=0.0, raw={"error": "could not generate fingerprint"})
    except acoustid.WebServiceError as e:
        return SourceResult(source="acoustid", confidence=0.0, raw={"error": f"AcoustID API error: {e}"})

    if not results or "results" not in results:
        return SourceResult(source="acoustid", confidence=0.0, raw={"note": "no results"})

    best_score = 0.0; best_recording = None
    for result in results.get("results", []):
        score = result.get("score", 0)
        recordings = result.get("recordings", [])
        if score > best_score and recordings:
            best_score = score; best_recording = recordings[0]

    if not best_recording:
        return SourceResult(source="acoustid", confidence=0.0, raw={"note": "matches found but no linked recordings"})

    artist = None; title = best_recording.get("title")
    artists = best_recording.get("artists", [])
    if artists: artist = artists[0].get("name")
    album = year = None; track = None
    releases = best_recording.get("releasegroups", [])
    if releases: album = releases[0].get("title")
    if not album:
        direct = best_recording.get("releases", [])
        if direct:
            rel = direct[0]; album = rel.get("title")
            date = rel.get("date", {})
            if isinstance(date, dict): year = str(date.get("year", "")) or None
            elif isinstance(date, str) and date: year = date[:4]
            mediums = rel.get("mediums", [])
            if mediums:
                tracks = mediums[0].get("tracks", [])
                if tracks: track = tracks[0].get("position")

    mb_id = best_recording.get("id")
    return SourceResult(source="acoustid", artist=artist, title=title, album=album, year=year,
                        track=track, confidence=round(best_score, 2),
                        raw={"musicbrainz_recording_id": mb_id, "acoustid_score": best_score})
