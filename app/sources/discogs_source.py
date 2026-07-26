import re, discogs_client
from discogs_client.exceptions import HTTPError
from models import SourceResult

def lookup_discogs(artist=None, title=None, album=None, token=None):
    if not token:
        return SourceResult(source="discogs", confidence=0.0, raw={"note": "no Discogs token — skipping"})
    client = discogs_client.Client("Tagicus/0.1.0", user_token=token)
    qp = []
    if artist: qp.append(artist)
    if title: qp.append(title)
    if not qp:
        return SourceResult(source="discogs", confidence=0.0, raw={"note": "no search criteria"})
    query = " ".join(qp)
    try:
        results = client.search(query, type="release")
        if results.count == 0:
            return SourceResult(source="discogs", confidence=0.0, raw={"note": "no results found"})
    except HTTPError as e:
        msg = str(e)
        if "401" in msg: msg = "Auth failed. Use 'Generate new token' at discogs.com/settings/developers"
        return SourceResult(source="discogs", confidence=0.0, raw={"error": f"Discogs: {msg}"})
    except Exception as e:
        return SourceResult(source="discogs", confidence=0.0, raw={"error": str(e)})

    try:
        release = results[0]
        fa = None; falb = release.title if hasattr(release, "title") else None
        fy = str(release.year) if hasattr(release, "year") and release.year else None
        fg = None; ft = title
        if hasattr(release, "artists") and release.artists:
            fa = release.artists[0].name
            if fa: fa = re.sub(r"\s*\(\d+\)\s*$", "", fa)
        if falb and fa:
            pp = re.escape(fa) + r"\s*(\(\d+\))?\s*-\s*"
            falb = re.sub(f"^{pp}", "", falb)
            if hasattr(release, "artists") and release.artists:
                rn = release.artists[0].name
                if rn and rn != fa:
                    pp2 = re.escape(rn) + r"\s*-\s*"
                    falb = re.sub(f"^{pp2}", "", falb)
        if hasattr(release, "genres") and release.genres: fg = release.genres[0]
        ftr = None
        if title and hasattr(release, "tracklist"):
            for i, track in enumerate(release.tracklist):
                if hasattr(track, "title") and track.title:
                    from thefuzz import fuzz
                    if fuzz.ratio(title.lower(), track.title.lower()) > 80:
                        pos = track.position if hasattr(track, "position") else None
                        if pos:
                            try: ftr = int(pos)
                            except: ftr = i + 1
                        break
        conf = 0.65 if fa and falb else 0.6
        return SourceResult(source="discogs", artist=fa, title=ft, album=falb, year=fy,
                            track=ftr, genre=fg, confidence=conf, raw={"query": query})
    except Exception as e:
        return SourceResult(source="discogs", confidence=0.0, raw={"error": str(e)})
