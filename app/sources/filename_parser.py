import os, re
from models import SourceResult

FILENAME_PATTERNS = [
    re.compile(r"^(?P<artist>.+?)\s*-\s*(?P<album>.+?)\s*-\s*(?P<track>\d{1,3})\s*-\s*(?P<title>.+)$"),
    re.compile(r"^(?P<track>\d{1,3})\s*-\s*(?P<artist>.+?)\s*-\s*(?P<title>.+)$"),
    re.compile(r"^(?P<artist>.+?)\s*[-~]\s*(?P<title>.+)$"),
    re.compile(r"^(?P<track>\d{1,3})[.\s]+(?P<title>.+)$"),
]

def parse_filename(filepath):
    basename = os.path.splitext(os.path.basename(filepath))[0].strip()
    dirpath = os.path.dirname(os.path.abspath(filepath))
    folders = dirpath.split(os.sep)
    artist = title = album = None; track = None; year = None

    year_match = re.search(r"\((\d{4})\)\s*$", basename)
    if year_match:
        year = year_match.group(1)
        basename = basename[:year_match.start()].strip()

    # Multi-disc rips often prefix the filename with "disc-track" (e.g.
    # "1-06 Artist - Title"). The patterns below expect a single plain track
    # number, so without this they misread the "-06" half as the start of
    # "artist - title" and glue the "06" onto the artist. Peel the disc-track
    # pair off first and keep just the track half.
    disc_track_match = re.match(r"^\d{1,2}-(\d{1,3})\s+(.+)$", basename)
    if disc_track_match:
        try:
            track = int(disc_track_match.group(1))
        except ValueError:
            track = None
        basename = disc_track_match.group(2).strip()

    for pattern in FILENAME_PATTERNS:
        match = pattern.match(basename)
        if match:
            g = match.groupdict()
            artist, title, album = g.get("artist"), g.get("title"), g.get("album")
            ts = g.get("track")
            if ts and track is None:
                try: track = int(ts)
                except: pass
            break
    if not title: title = basename

    skip = {"music","audio","mp3","downloads","media","songs","library","navidrome","data","tagicus"}
    useful = [f for f in folders if f.lower() not in skip and f != "" and f != os.sep]
    if len(useful) >= 2:
        if not artist: artist = useful[-2]
        if not album: album = useful[-1]
    elif len(useful) == 1:
        if not artist: artist = useful[-1]

    artist = _clean(artist); title = _clean(title); album = _clean(album)
    filled = sum(1 for v in [artist, title, album, track, year] if v)
    return SourceResult(source="filename", artist=artist, title=title, album=album, year=year,
                        track=track, confidence=min(filled / 6, 0.5),
                        raw={"original_filename": basename, "folder_path": dirpath, "useful_folders": useful})

def _clean(value):
    if not value: return None
    value = value.strip(" ._-")
    value = re.sub(r"\s*[\[\(]\d{2,3}\s*k?bps[\]\)]?\s*$", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s*[\[\(]\d{3}[\]\)]\s*$", "", value)
    value = value.strip()
    return value if value else None
