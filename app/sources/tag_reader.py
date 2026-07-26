import os, mutagen
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.flac import FLAC
from mutagen.oggvorbis import OggVorbis
from mutagen.apev2 import APEv2
from models import SourceResult

def read_tags(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    try:
        if ext == ".mp3": return _read_id3(filepath)
        elif ext in (".m4a", ".mp4", ".aac"): return _read_mp4(filepath)
        elif ext == ".flac": return _read_vorbis(filepath, FLAC)
        elif ext in (".ogg", ".opus"): return _read_vorbis(filepath, OggVorbis)
        elif ext == ".ape": return _read_ape(filepath)
        else: return _read_generic(filepath)
    except Exception as e:
        return SourceResult(source="id3_tags", confidence=0.0, raw={"error": str(e)})

def _read_id3(fp):
    audio = MP3(fp); tags = audio.tags
    if tags is None: return SourceResult(source="id3_tags", confidence=0.0)
    artist = _gid3(tags,"TPE1"); title = _gid3(tags,"TIT2"); album = _gid3(tags,"TALB")
    genre = _gid3(tags,"TCON"); year = _gid3(tags,"TDRC") or _gid3(tags,"TYER")
    track = _pt(_gid3(tags,"TRCK"))
    return _build(artist, title, album, year, track, genre)

def _read_mp4(fp):
    audio = MP4(fp); tags = audio.tags
    if tags is None: return SourceResult(source="id3_tags", confidence=0.0)
    artist = _gmp4(tags,"\xa9ART"); title = _gmp4(tags,"\xa9nam"); album = _gmp4(tags,"\xa9alb")
    genre = _gmp4(tags,"\xa9gen"); year = _gmp4(tags,"\xa9day")
    track = None
    if "trkn" in tags and tags["trkn"]:
        try: track = tags["trkn"][0][0]
        except: pass
    return _build(artist, title, album, year, track, genre)

def _read_vorbis(fp, cls):
    audio = cls(fp)
    return _build(_gv(audio,"artist"), _gv(audio,"title"), _gv(audio,"album"),
                  _gv(audio,"date"), _pt(_gv(audio,"tracknumber")), _gv(audio,"genre"))

def _read_ape(fp):
    try: tags = APEv2(fp)
    except: return SourceResult(source="id3_tags", confidence=0.0, raw={"note": "no APE tags found"})
    return _build(str(tags.get("Artist","")).strip() or None, str(tags.get("Title","")).strip() or None,
                  str(tags.get("Album","")).strip() or None, str(tags.get("Year","")).strip() or None,
                  _pt(str(tags.get("Track","")).strip() or None), str(tags.get("Genre","")).strip() or None)

def _read_generic(fp):
    audio = mutagen.File(fp, easy=True)
    if audio is None or audio.tags is None: return SourceResult(source="id3_tags", confidence=0.0)
    return _build(_ge(audio,"artist"), _ge(audio,"title"), _ge(audio,"album"),
                  _ge(audio,"date"), _pt(_ge(audio,"tracknumber")), _ge(audio,"genre"))

def _gid3(tags, key):
    if key in tags:
        try: val = str(tags[key].text[0]).strip(); return val if val else None
        except: return None
    return None

def _gmp4(tags, key):
    if key in tags and tags[key]:
        try: val = str(tags[key][0]).strip(); return val if val else None
        except: return None
    return None

def _gv(audio, key):
    vals = audio.get(key)
    if vals:
        val = str(vals[0]).strip(); return val if val else None
    return None

_ge = _gv

def _pt(raw):
    if not raw: return None
    try: return int(str(raw).split("/")[0])
    except: return None

def _build(artist, title, album, year, track, genre):
    filled = sum(1 for v in [artist, title, album, year, track, genre] if v)
    return SourceResult(source="id3_tags", artist=artist, title=title, album=album,
                        year=str(year) if year else None, track=track, genre=genre,
                        confidence=min(filled / 6, 0.8))
