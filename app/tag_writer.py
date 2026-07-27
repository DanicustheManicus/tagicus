"""
Tagicus - Tag Writer

Writes approved metadata back to audio files.
Respects settings for:
- Which fields to write
- Whether to clear existing tags
- Preserving artwork and lyrics
- File organization patterns
- Empty folder cleanup
"""

import os, shutil, re
import mutagen
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.flac import FLAC
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TRCK, TCON, APIC
from mutagen.apev2 import APEv2
import database as db
import paths


def apply_tags(song_id, organize=None, base_path=None):
    song = db.get_song(song_id)
    if not song:
        return {"error": "Song not found"}

    filepath = song["filepath"]
    if not os.path.exists(paths.long_path(filepath)):
        return {"error": f"File not found: {filepath}"}

    fields = song["fields"]
    artist = fields.get("artist", {}).get("value")
    title = fields.get("title", {}).get("value")
    album = fields.get("album", {}).get("value")
    year = fields.get("year", {}).get("value")
    track = fields.get("track", {}).get("value")
    genre = fields.get("genre", {}).get("value")

    # Load settings
    settings = db.get_all_settings()
    s = lambda k: settings.get(k) == "true"

    if organize is None:
        organize = s("organize_enabled")

    if organize and not base_path:
        base_path = _resolve_base_path(song)

    ext = os.path.splitext(filepath)[1].lower()

    # Determine which fields to write
    write = {
        "artist": artist if s("write_artist") else None,
        "title": title if s("write_title") else None,
        "album": album if s("write_album") else None,
        "year": year if s("write_year") else None,
        "track": track if s("write_track") else None,
        "genre": genre if s("write_genre") else None,
    }

    try:
        safe_filepath = paths.long_path(filepath)
        if ext == ".mp3":
            _write_mp3(safe_filepath, write, settings)
        elif ext in (".m4a", ".mp4", ".aac"):
            _write_mp4(safe_filepath, write, settings)
        elif ext == ".flac":
            _write_flac(safe_filepath, write, settings)
        else:
            _write_generic(safe_filepath, write, settings)
    except Exception as e:
        return {"error": f"Failed to write tags: {e}"}

    new_path = filepath
    if organize and base_path:
        try:
            new_path = _organize_file(
                filepath, artist, title, album, year, track, ext,
                base_path, settings
            )
        except Exception as e:
            # Tags were already written above even though the move failed,
            # so surface this distinctly rather than pretending nothing happened.
            return {"error": f"Tags written, but failed to move/rename file: {e}"}
        db.mark_organized(song_id)

    if new_path != filepath:
        db.update_filepath(song_id, new_path)
    db.mark_applied(song_id)
    return {"success": True, "filepath": new_path}


def _extract_artwork_mp3(tags):
    """Extract APIC (artwork) frames from ID3 tags."""
    artwork = []
    if tags:
        for key in list(tags.keys()):
            if key.startswith("APIC"):
                artwork.append(tags[key])
    return artwork


def _extract_lyrics_mp3(tags):
    """Extract USLT (lyrics) frames from ID3 tags."""
    lyrics = []
    if tags:
        for key in list(tags.keys()):
            if key.startswith("USLT"):
                lyrics.append(tags[key])
    return lyrics


def _write_mp3(filepath, write, settings):
    s = lambda k: settings.get(k) == "true"

    audio = MP3(filepath)
    tags = audio.tags

    # Save artwork and lyrics before clearing
    saved_artwork = []
    saved_lyrics = []
    if tags:
        if s("preserve_artwork"):
            saved_artwork = _extract_artwork_mp3(tags)
        if s("preserve_lyrics"):
            saved_lyrics = _extract_lyrics_mp3(tags)

    # Remove APEv2 from MP3 if enabled
    if s("remove_apev2_from_mp3"):
        try:
            ape = APEv2(filepath)
            ape.delete()
        except Exception:
            pass

    if s("clear_tags"):
        audio.delete()
        audio.save()
        audio = MP3(filepath)
        try:
            audio.add_tags()
        except Exception:
            pass
        tags = audio.tags
    else:
        if tags is None:
            try:
                audio.add_tags()
            except Exception:
                pass
            tags = audio.tags

    # Write fields
    if write["artist"]:
        tags.add(TPE1(encoding=3, text=[write["artist"]]))
    if write["title"]:
        tags.add(TIT2(encoding=3, text=[write["title"]]))
    if write["album"]:
        tags.add(TALB(encoding=3, text=[write["album"]]))
    if write["year"]:
        tags.add(TDRC(encoding=3, text=[str(write["year"])]))
    if write["track"]:
        tags.add(TRCK(encoding=3, text=[str(write["track"])]))
    if write["genre"]:
        tags.add(TCON(encoding=3, text=[write["genre"]]))
    # Write lyrics if available (skip the network round-trip if we're about
    # to restore lyrics the file already had - fetching would be redundant).
    if settings.get("fetch_lyrics") == "true" and not saved_lyrics:
        try:
            from sources.lrclib_source import fetch_lyrics
            lyrics_data = fetch_lyrics(artist=write["artist"], title=write["title"], album=write["album"])
            if lyrics_data.get("found"):
                from mutagen.id3 import USLT, SYLT
                prefer_synced = settings.get("prefer_synced_lyrics") == "true"
                if prefer_synced and lyrics_data.get("synced"):
                    tags.add(USLT(encoding=3, lang="eng", desc="synced", text=lyrics_data["synced"]))
                elif lyrics_data.get("plain"):
                    tags.add(USLT(encoding=3, lang="eng", desc="", text=lyrics_data["plain"]))
        except Exception:
            pass

    # Restore artwork and lyrics
    for art in saved_artwork:
        tags.add(art)
    for lyric in saved_lyrics:
        tags.add(lyric)

    audio.save()


def _write_mp4(filepath, write, settings):
    s = lambda k: settings.get(k) == "true"

    audio = MP4(filepath)

    # Save artwork before clearing
    saved_artwork = None
    if s("preserve_artwork") and audio.tags and "covr" in audio.tags:
        saved_artwork = audio.tags["covr"]

    if s("clear_tags"):
        audio.delete()
        audio.save()
        audio = MP4(filepath)
        if audio.tags is None:
            audio.tags = mutagen.mp4.MP4Tags()

    if write["artist"]:
        audio["\xa9ART"] = [write["artist"]]
    if write["title"]:
        audio["\xa9nam"] = [write["title"]]
    if write["album"]:
        audio["\xa9alb"] = [write["album"]]
    if write["year"]:
        audio["\xa9day"] = [str(write["year"])]
    if write["genre"]:
        audio["\xa9gen"] = [write["genre"]]
    if write["track"]:
        try:
            audio["trkn"] = [(int(write["track"]), 0)]
        except Exception:
            pass

    # Restore artwork
    if saved_artwork:
        audio["covr"] = saved_artwork

    audio.save()


def _write_flac(filepath, write, settings):
    s = lambda k: settings.get(k) == "true"

    audio = FLAC(filepath)

    # Remove ID3 from FLAC if enabled
    if s("remove_id3_from_flac"):
        try:
            if audio.tags is None:
                pass
            # FLAC files sometimes have ID3 tags prepended
            from mutagen.id3 import ID3
            try:
                id3 = ID3(filepath)
                id3.delete()
            except Exception:
                pass
        except Exception:
            pass

    # Save artwork (FLAC stores pictures separately)
    saved_pictures = []
    if s("preserve_artwork") and audio.pictures:
        saved_pictures = list(audio.pictures)

    if s("clear_tags"):
        audio.delete()
        audio.clear_pictures()

    if write["artist"]:
        audio["artist"] = write["artist"]
    if write["title"]:
        audio["title"] = write["title"]
    if write["album"]:
        audio["album"] = write["album"]
    if write["year"]:
        audio["date"] = str(write["year"])
    if write["track"]:
        audio["tracknumber"] = str(write["track"])
    if write["genre"]:
        audio["genre"] = write["genre"]

    # Restore artwork
    for pic in saved_pictures:
        audio.add_picture(pic)

    audio.save()


def _write_generic(filepath, write, settings):
    s = lambda k: settings.get(k) == "true"

    audio = mutagen.File(filepath, easy=True)
    if audio is None:
        return

    if s("clear_tags"):
        audio.delete()
        audio.save()
        audio = mutagen.File(filepath, easy=True)

    if write["artist"]:
        audio["artist"] = write["artist"]
    if write["title"]:
        audio["title"] = write["title"]
    if write["album"]:
        audio["album"] = write["album"]
    if write["year"]:
        audio["date"] = str(write["year"])
    if write["track"]:
        audio["tracknumber"] = str(write["track"])
    if write["genre"]:
        audio["genre"] = write["genre"]

    audio.save()


def _resolve_base_path(song):
    """Default organize target: the song's own library root, or its current folder if unassigned."""
    library_id = song.get("library_id")
    if library_id:
        lib = db.get_library(library_id)
        if lib:
            return lib["path"]
    return os.path.dirname(song["filepath"])


_long_path = paths.long_path


def _organize_file(filepath, artist, title, album, year, track, ext, base_path, settings):
    """Move file into organized folder structure using configured patterns."""

    folder_pattern = settings.get("folder_pattern", "{artist}/{album} ({year})")
    file_pattern = settings.get("file_pattern", "{track} - {artist} - {title}")

    # Build replacement values
    vals = {
        "artist": _safe_name(artist or "Unknown Artist"),
        "title": _safe_name(title or "Unknown"),
        "album": _safe_name(album or "Unknown Album"),
        "year": str(year) if year else "Unknown Year",
        "track": str(track).zfill(2) if track else "00",
        "genre": _safe_name(genre) if (genre := db.get_song_field_value(filepath, "genre")) else "Unknown Genre",
    }

    # Apply folder pattern
    try:
        folder = folder_pattern.format(**vals)
    except KeyError:
        folder = f"{vals['artist']}/{vals['album']} ({vals['year']})"

    # Apply file pattern
    try:
        new_name = file_pattern.format(**vals) + ext
    except KeyError:
        new_name = f"{vals['track']} - {vals['artist']} - {vals['title']}{ext}"

    new_dir = os.path.join(base_path, folder)
    os.makedirs(_long_path(new_dir), exist_ok=True)

    new_path = os.path.join(new_dir, new_name)

    # Don't overwrite existing files
    if os.path.exists(_long_path(new_path)) and os.path.abspath(new_path) != os.path.abspath(filepath):
        base, ext_part = os.path.splitext(new_path)
        counter = 1
        while os.path.exists(_long_path(new_path)):
            new_path = f"{base} ({counter}){ext_part}"
            counter += 1

    if os.path.abspath(new_path) != os.path.abspath(filepath):
        old_dir = os.path.dirname(filepath)
        shutil.move(_long_path(filepath), _long_path(new_path))
        if settings.get("cleanup_empty_folders") == "true":
            _cleanup_empty_dirs(old_dir, stop_dir=base_path)

    return new_path


def _cleanup_empty_dirs(path, stop_dir=None):
    """Remove empty folders walking upward, never deleting stop_dir itself or above it.

    If stop_dir is unknown, only the immediate folder is considered, to avoid
    climbing outside the library into unrelated parts of the filesystem.
    """
    if not path:
        return
    path = os.path.abspath(path)
    stop_dir = os.path.abspath(stop_dir) if stop_dir else None

    while path and path != stop_dir:
        parent = os.path.dirname(path)
        if parent == path:
            break
        try:
            if os.path.isdir(_long_path(path)) and not os.listdir(_long_path(path)):
                os.rmdir(_long_path(path))
                path = parent
            else:
                break
        except OSError:
            break
        if stop_dir is None:
            break


def _safe_name(name):
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = name.strip('. ')
    return name[:200]
