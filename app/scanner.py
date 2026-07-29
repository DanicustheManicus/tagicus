"""
Tagicus - Scanner

Runs all sources against a file and saves results to the database.
Respects settings for which sources are enabled and review threshold.
"""

import os, glob, time
from concurrent.futures import ThreadPoolExecutor
from thefuzz import fuzz
from models import SourceResult
from config import load_config, get_key
import paths
from sources.tag_reader import read_tags
from sources.filename_parser import parse_filename
from sources.acoustid_source import lookup_acoustid
from sources.musicbrainz_source import lookup_musicbrainz
from sources.discogs_source import lookup_discogs
from sources.deezer_source import lookup_deezer
from sources.audiodb_source import lookup_audiodb
from sources.wikidata_source import lookup_wikidata
from sources.openopus_source import lookup_openopus
from sources.vgmdb_source import lookup_vgmdb
from sources.vocadb_source import lookup_vocadb
from sources.metallum_source import lookup_metallum
from sources.compare import cross_reference
import database as db

AUDIO_EXTENSIONS = ["mp3", "m4a", "flac", "ogg", "ape", "wma", "wav", "aac", "opus"]


def scan_file(filepath, config=None, settings=None):
    if config is None:
        config = load_config()
    if settings is None:
        settings = db.get_all_settings()

    s = lambda k: settings.get(k) == "true"
    filename = os.path.basename(filepath)
    results = []

    d = db.get_db()
    existing = d.execute(
        "SELECT status, organized FROM songs WHERE filepath = ?", (filepath,)
    ).fetchone()
    d.close()

    # Skip files already scanned and done (unless full rescan)
    if not config.get("_full_rescan"):
        if existing and existing["status"] == "done":
            return None

    # --- Local sources (always run) ---
    tag_result = read_tags(filepath)
    results.append(tag_result)

    # If Tagicus itself generated this filename from the current tags (via
    # organize), it's not independent corroboration - it's the app echoing
    # its own last write, and would let a bad edit "confirm itself" forever.
    filename_result = parse_filename(filepath)
    if not (existing and existing["organized"]):
        results.append(filename_result)

    local_artist = _pick_from_locals([tag_result, filename_result], "artist")
    local_title = _pick_from_locals([tag_result, filename_result], "title")

    # --- AcoustID fingerprint ---
    acoustid_key = get_key(config, "acoustid") if s("source_acoustid") else None
    mb_recording_id = None
    acoustid_artist = None
    acoustid_title = None

    if acoustid_key:
        ar = lookup_acoustid(filepath, acoustid_key)
        results.append(ar)
        mb_recording_id = ar.raw.get("musicbrainz_recording_id")
        acoustid_artist = ar.artist
        acoustid_title = ar.title

    # --- Determine if locals and AcoustID disagree ---
    locals_and_acoustid_agree = _sources_agree(
        local_artist, acoustid_artist, local_title, acoustid_title
    )

    # --- Online sources ---
    discogs_token = get_key(config, "discogs") if s("source_discogs") else None

    if locals_and_acoustid_agree or not local_artist:
        best_artist = acoustid_artist or local_artist
        best_title = acoustid_title or local_title
        results.extend(_search_online(
            best_artist, best_title, mb_recording_id, discogs_token, config, settings
        ))
    else:
        if acoustid_artist or acoustid_title:
            results.extend(_search_online(
                acoustid_artist, acoustid_title, mb_recording_id, discogs_token, config, settings
            ))
        if local_artist or local_title:
            results.extend(_search_online_local_path(
                local_artist, local_title, discogs_token, config, settings
            ))

    # Cross-reference
    votes = cross_reference(results)

    # Determine status using threshold from settings
    threshold = db.setting_float("review_threshold")
    artist_vote = next((v for v in votes if v.field_name == "artist"), None)
    title_vote = next((v for v in votes if v.field_name == "title"), None)

    artist_ok = artist_vote and artist_vote.best_value is not None
    title_ok = title_vote and title_vote.best_value is not None

    if not artist_ok or not title_ok:
        status = "needs_attention"
    elif (artist_vote.conflict and artist_vote.agreement < threshold) or \
         (title_vote.conflict and title_vote.agreement < threshold):
        status = "review"
    else:
        status = "ready"

    # Save to database (pass status directly)
    song_id = _save_with_status(filepath, filename, results, votes, status)
    return song_id


def _save_with_status(filepath, filename, results, votes, status):
    """Save scan result with pre-calculated status."""
    d = db.get_db()
    has_artwork = db._check_artwork(filepath)
    library_id = db.find_library_for_path(filepath)

    d.execute("""
        INSERT INTO songs (filepath, filename, library_id, status, has_artwork, updated_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(filepath) DO UPDATE SET
            filename = excluded.filename,
            library_id = excluded.library_id,
            status = excluded.status,
            has_artwork = excluded.has_artwork,
            updated_at = datetime('now')
    """, (filepath, filename, library_id, status, has_artwork))
    d.commit()

    song_id = d.execute("SELECT id FROM songs WHERE filepath = ?", (filepath,)).fetchone()["id"]

    FIELDS = ["artist", "title", "album", "year", "track", "genre"]
    for vote in votes:
        d.execute("""
            INSERT INTO song_fields (song_id, field_name, best_value, conflict, agreement)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(song_id, field_name) DO UPDATE SET
                best_value = excluded.best_value,
                conflict = excluded.conflict,
                agreement = excluded.agreement
        """, (song_id, vote.field_name, vote.best_value, vote.conflict, vote.agreement))

    for result in results:
        for field_name in FIELDS:
            value = getattr(result, field_name, None)
            if value is not None:
                d.execute("""
                    INSERT INTO song_votes (song_id, field_name, source_name, value, confidence)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(song_id, field_name, source_name) DO UPDATE SET
                        value = excluded.value,
                        confidence = excluded.confidence
                """, (song_id, field_name, result.source, str(value), result.confidence))

    d.commit()
    d.close()
    return song_id


def _run_parallel(jobs):
    """Run independent source lookups at the same time instead of one after
    another. Each job is a zero-arg callable; a failing job is dropped
    exactly like the old sequential try/except did, it just doesn't block
    the others from running while it's in flight."""
    if not jobs:
        return []
    results = []
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futures = [pool.submit(job) for job in jobs]
        for f in futures:
            try:
                results.append(f.result())
            except Exception:
                pass
    return results


def _search_online(artist, title, mb_recording_id, discogs_token, config, settings):
    s = lambda k: settings.get(k) == "true"
    results = []

    # These don't depend on each other's results, so they can all run at
    # the same time instead of waiting on one another's network round-trip.
    independent_jobs = []
    if s("source_musicbrainz") and (mb_recording_id or artist or title):
        independent_jobs.append(lambda: lookup_musicbrainz(artist=artist, title=title, recording_id=mb_recording_id))
    if discogs_token and (artist or title):
        independent_jobs.append(lambda: lookup_discogs(artist=artist, title=title, token=discogs_token))
    if s("source_deezer") and (artist or title):
        independent_jobs.append(lambda: lookup_deezer(artist=artist, title=title))
    if s("source_audiodb") and artist and title:
        independent_jobs.append(lambda: lookup_audiodb(artist=artist, title=title))
    if s("source_openopus") and artist:
        independent_jobs.append(lambda: lookup_openopus(artist=artist, title=title))
    if s("source_vocadb") and title:
        independent_jobs.append(lambda: lookup_vocadb(artist=artist, title=title))
    if s("source_metallum") and title:
        independent_jobs.append(lambda: lookup_metallum(artist=artist, title=title))

    results.extend(_run_parallel(independent_jobs))

    best_album = None
    for r in results:
        if r.album:
            best_album = r.album
            break

    # Wikidata and VGMdb want the album the sources above found, so they
    # have to wait for that batch - but they can still run alongside
    # each other instead of one after the other.
    dependent_jobs = []
    if s("source_wikidata") and artist:
        dependent_jobs.append(lambda: lookup_wikidata(artist=artist, title=title, album=best_album))
    if s("source_vgmdb") and (artist or title):
        dependent_jobs.append(lambda: lookup_vgmdb(artist=artist, title=title, album=best_album))

    results.extend(_run_parallel(dependent_jobs))

    return results


def _search_online_local_path(artist, title, discogs_token, config, settings):
    s = lambda k: settings.get(k) == "true"

    # Nothing here depends on another source's result, so all of them can
    # run at the same time.
    jobs = []
    if s("source_musicbrainz") and (artist or title):
        jobs.append(lambda: lookup_musicbrainz(artist=artist, title=title, recording_id=None))
    if discogs_token and (artist or title):
        jobs.append(lambda: lookup_discogs(artist=artist, title=title, token=discogs_token))
    if s("source_deezer") and (artist or title):
        jobs.append(lambda: lookup_deezer(artist=artist, title=title))
    if s("source_audiodb") and artist and title:
        jobs.append(lambda: lookup_audiodb(artist=artist, title=title))
    if s("source_openopus") and artist:
        jobs.append(lambda: lookup_openopus(artist=artist, title=title))
    if s("source_vgmdb") and (artist or title):
        jobs.append(lambda: lookup_vgmdb(artist=artist, title=title))
    if s("source_vocadb") and title:
        jobs.append(lambda: lookup_vocadb(artist=artist, title=title))
    if s("source_metallum") and title:
        jobs.append(lambda: lookup_metallum(artist=artist, title=title))

    return _run_parallel(jobs)


def _pick_from_locals(local_results, field):
    for r in sorted(local_results, key=lambda r: r.confidence, reverse=True):
        val = getattr(r, field, None)
        if val:
            return val
    return None


def _sources_agree(local_artist, acoustid_artist, local_title, acoustid_title):
    if not acoustid_artist or not local_artist:
        return True
    return fuzz.ratio(
        (local_artist or "").lower(),
        (acoustid_artist or "").lower()
    ) >= 70


def scan_folder(folder_path, config=None):
    if config is None:
        config = load_config()
    settings = db.get_all_settings()

    audio_files = []
    for ext in AUDIO_EXTENSIONS:
        audio_files.extend(glob.glob(os.path.join(folder_path, "**", f"*.{ext}"), recursive=True))
        audio_files.extend(glob.glob(os.path.join(folder_path, "**", f"*.{ext.upper()}"), recursive=True))
    audio_files = sorted(set(audio_files))

    scanned = []
    for i, filepath in enumerate(audio_files):
        song_id = scan_file(filepath, config, settings)
        scanned.append(song_id)
        if i < len(audio_files) - 1:
            time.sleep(0.2)

    return scanned


def rescan_file(song_id, config=None):
    song = db.get_song(song_id)
    if not song:
        return None
    filepath = song["filepath"]
    if not os.path.exists(paths.long_path(filepath)):
        return None

    if config is None:
        config = load_config()
    settings = db.get_all_settings()
    s = lambda k: settings.get(k) == "true"

    fields = song.get("fields", {})
    hint_artist = None
    hint_title = None
    for f_name in ["artist", "title"]:
        f = fields.get(f_name, {})
        if f.get("user_edited") and f.get("value"):
            if f_name == "artist":
                hint_artist = f["value"]
            if f_name == "title":
                hint_title = f["value"]

    results = []
    tag_result = read_tags(paths.long_path(filepath))
    results.append(tag_result)

    # If Tagicus itself generated this filename from the current tags (via
    # organize), it isn't independent corroboration - it's the app echoing
    # its own last write. Counting it as a second "local" vote would let a
    # single bad edit "confirm itself" and permanently dodge conflict
    # detection. Only trust the filename when it predates/is independent of
    # our own organize step.
    filename_result = parse_filename(filepath)
    if not song.get("organized"):
        results.append(filename_result)

    local_artist = hint_artist or _pick_from_locals([tag_result, filename_result], "artist")
    local_title = hint_title or _pick_from_locals([tag_result, filename_result], "title")

    acoustid_key = get_key(config, "acoustid") if s("source_acoustid") else None
    mb_recording_id = None
    acoustid_artist = None
    acoustid_title = None
    if acoustid_key:
        ar = lookup_acoustid(filepath, acoustid_key)
        results.append(ar)
        mb_recording_id = ar.raw.get("musicbrainz_recording_id")
        acoustid_artist = ar.artist
        acoustid_title = ar.title

    discogs_token = get_key(config, "discogs") if s("source_discogs") else None

    if hint_artist or hint_title:
        results.extend(_search_online(
            local_artist, local_title, None, discogs_token, config, settings
        ))
        # Most sources effectively AND artist+title together, so a bad edit
        # to one field can drag an otherwise-findable match down to zero
        # results - hiding the very disagreement a rescan should catch. If
        # only one of the two was hand-edited, also search using just the
        # other, still-independently-sourced field, so a wrong artist can't
        # suppress a correct title (or vice versa) from surfacing a
        # genuinely contradicting vote.
        if hint_artist and not hint_title and local_title:
            results.extend(_search_online(
                None, local_title, None, discogs_token, config, settings
            ))
        elif hint_title and not hint_artist and local_artist:
            results.extend(_search_online(
                local_artist, None, None, discogs_token, config, settings
            ))
    elif _sources_agree(local_artist, acoustid_artist, local_title, acoustid_title):
        best_artist = acoustid_artist or local_artist
        best_title = acoustid_title or local_title
        results.extend(_search_online(
            best_artist, best_title, mb_recording_id, discogs_token, config, settings
        ))
    else:
        if acoustid_artist or acoustid_title:
            results.extend(_search_online(
                acoustid_artist, acoustid_title, mb_recording_id, discogs_token, config, settings
            ))
        if local_artist or local_title:
            results.extend(_search_online_local_path(
                local_artist, local_title, discogs_token, config, settings
            ))

    votes = cross_reference(results)

    threshold = db.setting_float("review_threshold")
    artist_vote = next((v for v in votes if v.field_name == "artist"), None)
    title_vote = next((v for v in votes if v.field_name == "title"), None)
    artist_ok = artist_vote and artist_vote.best_value is not None
    title_ok = title_vote and title_vote.best_value is not None
    if not artist_ok or not title_ok:
        status = "needs_attention"
    elif (artist_vote.conflict and artist_vote.agreement < threshold) or \
         (title_vote.conflict and title_vote.agreement < threshold):
        status = "review"
    else:
        status = "ready"

    _save_with_status(filepath, os.path.basename(filepath), results, votes, status)
    return song_id
