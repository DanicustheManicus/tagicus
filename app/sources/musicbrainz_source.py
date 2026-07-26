import time, musicbrainzngs
from models import SourceResult

musicbrainzngs.set_useragent("Tagicus", "0.1.0", "https://github.com/tagicus")
MAX_RETRIES = 3; RETRY_DELAY = 3

COMP_HINTS = ["best of","greatest hits","collection","anthology","compilation","archives",
    "complete","box set","live","concert","unplugged","session","demo","outtake","bootleg",
    "tribute","now that's what","now ","dad rocks","100 hits","50 hits","20 hits"]

def lookup_musicbrainz(artist=None, title=None, recording_id=None):
    if recording_id: return _lookup_by_id(recording_id)
    if artist or title: return _search_by_text(artist, title)
    return SourceResult(source="musicbrainz", confidence=0.0, raw={"note": "no search criteria"})

def _lookup_by_id(recording_id):
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = musicbrainzngs.get_recording_by_id(recording_id, includes=["artists", "releases"])
            break
        except musicbrainzngs.WebServiceError as e:
            last_error = e
            if attempt < MAX_RETRIES: time.sleep(RETRY_DELAY)
    else:
        return SourceResult(source="musicbrainz", confidence=0.0, raw={"error": f"API error after {MAX_RETRIES} retries: {last_error}"})

    rec = result.get("recording", {})
    title = rec.get("title"); artist = None
    ac = rec.get("artist-credit", [])
    if ac: artist = ac[0].get("name") or ac[0].get("artist", {}).get("name")
    album = year = None; track = None
    rl = rec.get("release-list", [])
    if rl:
        release = _pick_best_release(rl); album = release.get("title")
        date = release.get("date", "")
        if date: year = date[:4]
        ml = release.get("medium-list", [])
        if ml:
            tl = ml[0].get("track-list", [])
            if tl:
                try: track = int(tl[0].get("number", 0))
                except: pass
    genre = None; tags = rec.get("tag-list", [])
    if tags:
        st = sorted(tags, key=lambda t: int(t.get("count", 0)), reverse=True)
        genre = st[0].get("name")
    return SourceResult(source="musicbrainz", artist=artist, title=title, album=album, year=year,
                        track=track, genre=genre, confidence=0.9, raw={"recording_id": recording_id})

def _search_by_text(artist=None, title=None):
    qp = []
    if artist: qp.append(f'artist:"{artist}"')
    if title: qp.append(f'recording:"{title}"')
    query = " AND ".join(qp)
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = musicbrainzngs.search_recordings(query=query, limit=5); break
        except musicbrainzngs.WebServiceError as e:
            last_error = e
            if attempt < MAX_RETRIES: time.sleep(RETRY_DELAY)
    else:
        return SourceResult(source="musicbrainz", confidence=0.0, raw={"error": f"search error after {MAX_RETRIES} retries: {last_error}"})

    recs = result.get("recording-list", [])
    if not recs: return SourceResult(source="musicbrainz", confidence=0.0, raw={"note": "no results found", "query": query})
    rec = recs[0]; ms = int(rec.get("ext:score", 0))
    ft = rec.get("title"); fa = None
    ac = rec.get("artist-credit", [])
    if ac: fa = ac[0].get("name") or ac[0].get("artist", {}).get("name")
    falb = fy = None; rl = rec.get("release-list", [])
    if rl:
        release = _pick_best_release(rl); falb = release.get("title")
        date = release.get("date", "")
        if date: fy = date[:4]
    conf = min(ms / 100 * 0.7, 0.7)
    return SourceResult(source="musicbrainz", artist=fa, title=ft, album=falb, year=fy, confidence=round(conf, 2),
                        raw={"recording_id": rec.get("id"), "query": query})

def _pick_best_release(release_list):
    def is_comp(r):
        t = r.get("title", "").lower()
        return any(h in t for h in COMP_HINTS)
    official = [r for r in release_list if r.get("status") == "Official"]
    cands = official if official else release_list
    nc = [r for r in cands if not is_comp(r)]
    if nc: cands = nc
    def sk(r):
        rg = r.get("release-group", {}); rt = (rg.get("type") or "").lower()
        sec = [s.lower() for s in rg.get("secondary-type-list", [])]
        if "compilation" in sec or "live" in sec: return (3, r.get("date", "9999"))
        if rt == "album": return (0, r.get("date", "9999"))
        if rt in ("single", "ep"): return (1, r.get("date", "9999"))
        return (2, r.get("date", "9999"))
    cands.sort(key=sk)
    return cands[0]
