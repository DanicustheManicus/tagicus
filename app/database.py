"""
Tagicus - Database Layer

SQLite database that persists scan results, user edits, and song state.
Stored at /data/tagicus.db so it survives container restarts.
"""

import sqlite3
import json
import os
from datetime import datetime
import paths

DB_PATH = paths.db_path()
FIELDS = ["artist", "title", "album", "year", "track", "genre"]


def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    return db


def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS libraries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            path TEXT UNIQUE NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filepath TEXT UNIQUE NOT NULL,
            filename TEXT NOT NULL,
            library_id INTEGER,
            status TEXT DEFAULT 'pending',
            has_artwork INTEGER DEFAULT 0,
            organized INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (library_id) REFERENCES libraries(id)
        );

        CREATE TABLE IF NOT EXISTS song_fields (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            song_id INTEGER NOT NULL,
            field_name TEXT NOT NULL,
            best_value TEXT,
            user_edited INTEGER DEFAULT 0,
            conflict INTEGER DEFAULT 0,
            agreement REAL DEFAULT 0.0,
            FOREIGN KEY (song_id) REFERENCES songs(id),
            UNIQUE(song_id, field_name)
        );

        CREATE TABLE IF NOT EXISTS song_votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            song_id INTEGER NOT NULL,
            field_name TEXT NOT NULL,
            source_name TEXT NOT NULL,
            value TEXT,
            confidence REAL DEFAULT 0.0,
            FOREIGN KEY (song_id) REFERENCES songs(id),
            UNIQUE(song_id, field_name, source_name)
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_song_fields_song_id ON song_fields(song_id);
        CREATE INDEX IF NOT EXISTS idx_song_votes_song_id ON song_votes(song_id);
        CREATE INDEX IF NOT EXISTS idx_songs_status ON songs(status);
        CREATE INDEX IF NOT EXISTS idx_songs_library_id ON songs(library_id);
    """)
    db.commit()

    # Migrate databases created before the 'organized' column existed.
    cols = {row["name"] for row in db.execute("PRAGMA table_info(songs)").fetchall()}
    if "organized" not in cols:
        db.execute("ALTER TABLE songs ADD COLUMN organized INTEGER DEFAULT 0")
        db.commit()

    db.close()


def save_scan_result(filepath, filename, results, votes):
    db = get_db()

    # Check for artwork
    has_artwork = _check_artwork(filepath)

    # Find which library this belongs to
    library_id = find_library_for_path(filepath)

    # Upsert song
    db.execute("""
        INSERT INTO songs (filepath, filename, library_id, has_artwork, updated_at)
        VALUES (?, ?, ?, ?, datetime('now'))
        ON CONFLICT(filepath) DO UPDATE SET
            filename = excluded.filename,
            library_id = excluded.library_id,
            has_artwork = excluded.has_artwork,
            updated_at = datetime('now')
        """, (filepath, filename, library_id, has_artwork))
    db.commit()

    song_id = db.execute("SELECT id FROM songs WHERE filepath = ?", (filepath,)).fetchone()["id"]

    # Save field verdicts
    for vote in votes:
        db.execute("""
            INSERT INTO song_fields (song_id, field_name, best_value, conflict, agreement)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(song_id, field_name) DO UPDATE SET
                best_value = excluded.best_value,
                conflict = excluded.conflict,
                agreement = excluded.agreement
        """, (song_id, vote.field_name, vote.best_value, vote.conflict, vote.agreement))

    # Save individual source votes
    for result in results:
        for field_name in FIELDS:
            value = getattr(result, field_name, None)
            if value is not None:
                db.execute("""
                    INSERT INTO song_votes (song_id, field_name, source_name, value, confidence)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(song_id, field_name, source_name) DO UPDATE SET
                        value = excluded.value,
                        confidence = excluded.confidence
                """, (song_id, field_name, result.source, str(value), result.confidence))

    db.commit()
    db.close()
    return song_id


def get_all_songs(status_filter=None):
    db = get_db()
    if status_filter and status_filter != "all":
        songs = db.execute(
            "SELECT * FROM songs WHERE status = ? ORDER BY updated_at DESC",
            (status_filter,)
        ).fetchall()
    else:
        songs = db.execute("SELECT * FROM songs ORDER BY updated_at DESC").fetchall()

    # Fetch all fields/votes once instead of two queries per song (was N+1,
    # and with no index this used to be a full table scan per song).
    fields_by_song = {}
    for f in db.execute("SELECT * FROM song_fields").fetchall():
        fields_by_song.setdefault(f["song_id"], []).append(f)

    votes_by_song_field = {}
    for v in db.execute("SELECT * FROM song_votes").fetchall():
        key = (v["song_id"], v["field_name"])
        votes_by_song_field.setdefault(key, {})[v["source_name"]] = v["value"]

    result = []
    for song in songs:
        song_data = dict(song)
        song_data["fields"] = {}
        for f in fields_by_song.get(song["id"], []):
            song_data["fields"][f["field_name"]] = {
                "value": f["best_value"],
                "conflict": bool(f["conflict"]),
                "agreement": f["agreement"],
                "user_edited": bool(f["user_edited"]),
                "votes": votes_by_song_field.get((song["id"], f["field_name"]), {}),
            }

        result.append(song_data)

    db.close()
    return result


def get_song(song_id):
    db = get_db()
    song = db.execute("SELECT * FROM songs WHERE id = ?", (song_id,)).fetchone()
    if not song:
        db.close()
        return None

    fields = db.execute(
        "SELECT * FROM song_fields WHERE song_id = ?", (song_id,)
    ).fetchall()

    votes = db.execute(
        "SELECT * FROM song_votes WHERE song_id = ?", (song_id,)
    ).fetchall()

    song_data = dict(song)
    song_data["fields"] = {}
    for f in fields:
        field_votes = {}
        for v in votes:
            if v["field_name"] == f["field_name"]:
                field_votes[v["source_name"]] = v["value"]
        song_data["fields"][f["field_name"]] = {
            "value": f["best_value"],
            "conflict": bool(f["conflict"]),
            "agreement": f["agreement"],
            "user_edited": bool(f["user_edited"]),
            "votes": field_votes,
        }

    db.close()
    return song_data


def update_field(song_id, field_name, value):
    db = get_db()
    db.execute("""
        UPDATE song_fields SET best_value = ?, user_edited = 1, conflict = 0
        WHERE song_id = ? AND field_name = ?
    """, (value, song_id, field_name))

    # Recompute song status
    fields = db.execute(
        "SELECT * FROM song_fields WHERE song_id = ?", (song_id,)
    ).fetchall()

    unknowns = sum(1 for f in fields if not f["best_value"])
    conflicts = sum(1 for f in fields if f["conflict"])
    if unknowns >= 2:
        status = "needs_attention"
    elif conflicts > 0:
        status = "review"
    else:
        status = "ready"

    db.execute(
        "UPDATE songs SET status = ?, updated_at = datetime('now') WHERE id = ?",
        (status, song_id)
    )
    db.commit()
    db.close()


def mark_applied(song_id):
    db = get_db()
    db.execute(
        "UPDATE songs SET status = 'done', updated_at = datetime('now') WHERE id = ?",
        (song_id,)
    )
    db.commit()
    db.close()


def mark_organized(song_id):
    """Flag that this song's current filename was generated by Tagicus's own
    organize step (from its own tag data), not independently sourced.

    Rescans must not treat such a filename as corroborating evidence for the
    tag it was derived from - that would be the app confirming itself rather
    than an independent check.
    """
    db = get_db()
    db.execute("UPDATE songs SET organized = 1 WHERE id = ?", (song_id,))
    db.commit()
    db.close()


def get_stats():
    db = get_db()
    total = db.execute("SELECT COUNT(*) as c FROM songs").fetchone()["c"]
    ready = db.execute("SELECT COUNT(*) as c FROM songs WHERE status = 'ready'").fetchone()["c"]
    done = db.execute("SELECT COUNT(*) as c FROM songs WHERE status = 'done'").fetchone()["c"]
    review = db.execute("SELECT COUNT(*) as c FROM songs WHERE status = 'review'").fetchone()["c"]
    needs = db.execute("SELECT COUNT(*) as c FROM songs WHERE status = 'needs_attention'").fetchone()["c"]
    no_art = db.execute("SELECT COUNT(*) as c FROM songs WHERE has_artwork = 0").fetchone()["c"]
    conflicts = db.execute("SELECT COUNT(DISTINCT song_id) as c FROM song_fields WHERE conflict = 1").fetchone()["c"]
    db.close()
    return {
        "total": total,
        "ready": ready,
        "done": done,
        "review": review,
        "needs_attention": needs,
        "missing_artwork": no_art,
        "conflicts": conflicts,
        "healthy": done + ready,
    }


def _check_artwork(filepath):
    try:
        import mutagen
        audio = mutagen.File(filepath)
        if audio is None:
            return 0
        # MP3
        if hasattr(audio, 'tags') and audio.tags:
            for key in audio.tags:
                if key.startswith("APIC"):
                    return 1
        # MP4/M4A
        if hasattr(audio, 'tags') and audio.tags and "covr" in audio.tags:
            return 1
        # FLAC
        if hasattr(audio, 'pictures') and audio.pictures:
            return 1
    except Exception:
        pass
    return 0


# --- Library Management ---

def add_library(name, path):
    db = get_db()
    try:
        db.execute("INSERT INTO libraries (name, path) VALUES (?, ?)", (name, path))
        db.commit()
        lib_id = db.execute("SELECT id FROM libraries WHERE path = ?", (path,)).fetchone()["id"]
        db.close()
        return lib_id
    except sqlite3.IntegrityError:
        db.close()
        return None


def get_libraries():
    db = get_db()
    libs = db.execute("SELECT * FROM libraries ORDER BY name").fetchall()
    result = []
    for lib in libs:
        song_count = db.execute(
            "SELECT COUNT(*) as c FROM songs WHERE library_id = ?", (lib["id"],)
        ).fetchone()["c"]
        d = dict(lib)
        d["song_count"] = song_count
        result.append(d)
    db.close()
    return result


def delete_library(lib_id):
    db = get_db()
    db.execute("DELETE FROM song_votes WHERE song_id IN (SELECT id FROM songs WHERE library_id = ?)", (lib_id,))
    db.execute("DELETE FROM song_fields WHERE song_id IN (SELECT id FROM songs WHERE library_id = ?)", (lib_id,))
    db.execute("DELETE FROM songs WHERE library_id = ?", (lib_id,))
    db.execute("DELETE FROM libraries WHERE id = ?", (lib_id,))
    db.commit()
    db.close()


def get_library(lib_id):
    db = get_db()
    lib = db.execute("SELECT * FROM libraries WHERE id = ?", (lib_id,)).fetchone()
    db.close()
    return dict(lib) if lib else None


def find_library_for_path(filepath):
    """Find which library a filepath belongs to."""
    db = get_db()
    libs = db.execute("SELECT * FROM libraries ORDER BY length(path) DESC").fetchall()
    db.close()
    for lib in libs:
        if filepath.startswith(lib["path"]):
            return lib["id"]
    return None


def find_duplicates():
    """Find songs that share the same artist + title."""
    d = get_db()
    dupes = d.execute("""
        SELECT sf1.best_value as artist, sf2.best_value as title,
               GROUP_CONCAT(s.id) as song_ids,
               GROUP_CONCAT(s.filename, '||') as filenames,
               COUNT(*) as count
        FROM songs s
        JOIN song_fields sf1 ON s.id = sf1.song_id AND sf1.field_name = 'artist'
        JOIN song_fields sf2 ON s.id = sf2.song_id AND sf2.field_name = 'title'
        WHERE sf1.best_value IS NOT NULL AND sf2.best_value IS NOT NULL
        GROUP BY LOWER(TRIM(sf1.best_value)), LOWER(TRIM(sf2.best_value))
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC
    """).fetchall()
    d.close()

    result = []
    for row in dupes:
        ids = [int(x) for x in row["song_ids"].split(",")]
        files = row["filenames"].split("||")
        result.append({
            "artist": row["artist"],
            "title": row["title"],
            "count": row["count"],
            "song_ids": ids,
            "filenames": files,
        })
    return result

DEFAULTS = {
    "organize_enabled": "true",
    "folder_pattern": "{artist}/{album} ({year})",
    "file_pattern": "{track} - {artist} - {title}",
    "review_threshold": "0.35",
    "source_acoustid": "true",
    "source_musicbrainz": "true",
    "source_discogs": "true",
    "source_deezer": "true",
    "source_audiodb": "true",
    "source_wikidata": "true",
    "source_openopus": "false",
    "source_vgmdb": "false",
    "source_vocadb": "false",
    "source_metallum": "false",
    "source_lrclib": "false",
    "clear_tags": "true",
    "preserve_artwork": "true",
    "preserve_lyrics": "true",
    "remove_id3_from_flac": "true",
    "remove_apev2_from_mp3": "true",
    "cleanup_empty_folders": "true",
    "write_artist": "true",
    "write_title": "true",
    "write_album": "true",
    "write_year": "true",
    "write_track": "true",
    "write_genre": "true",
    "fetch_lyrics": "true",
    "prefer_synced_lyrics": "true",
    "tutorial_done": "false",

}


def get_setting(key):
    d = get_db()
    row = d.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    d.close()
    if row:
        return row["value"]
    return DEFAULTS.get(key)


def get_all_settings():
    d = get_db()
    rows = d.execute("SELECT key, value FROM settings").fetchall()
    d.close()
    result = dict(DEFAULTS)
    for row in rows:
        result[row["key"]] = row["value"]
    return result


def set_setting(key, value):
    d = get_db()
    d.execute("""
        INSERT INTO settings (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (key, str(value)))
    d.commit()
    d.close()


def set_settings(updates):
    d = get_db()
    for key, value in updates.items():
        d.execute("""
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, str(value)))
    d.commit()
    d.close()


def setting_bool(key):
    return get_setting(key) == "true"


def setting_float(key):
    try:
        return float(get_setting(key))
    except (ValueError, TypeError):
        return float(DEFAULTS.get(key, "0"))


def get_song_field_value(filepath, field_name):
    """Get a field value for a song by filepath."""
    d = get_db()
    row = d.execute("""
        SELECT sf.best_value FROM song_fields sf
        JOIN songs s ON sf.song_id = s.id
        WHERE s.filepath = ? AND sf.field_name = ?
    """, (filepath, field_name)).fetchone()
    d.close()
    return row["best_value"] if row else None

def update_filepath(song_id, new_filepath):
    d = get_db()
    d.execute(
        "UPDATE songs SET filepath = ?, filename = ?, updated_at = datetime('now') WHERE id = ?",
        (new_filepath, os.path.basename(new_filepath), song_id)
    )
    d.commit()
    d.close() 

def cleanup_missing_files():
    """Remove database entries for files that no longer exist on disk."""
    d = get_db()
    songs = d.execute("SELECT id, filepath FROM songs").fetchall()
    removed = 0
    for song in songs:
        if not os.path.exists(song["filepath"]):
            d.execute("DELETE FROM song_votes WHERE song_id = ?", (song["id"],))
            d.execute("DELETE FROM song_fields WHERE song_id = ?", (song["id"],))
            d.execute("DELETE FROM songs WHERE id = ?", (song["id"],))
            removed += 1
    d.commit()
    d.close()
    return removed
