"""
Tagicus - Web Server

FastAPI app serving the API and frontend.
Access at http://mark3:8017
"""

import os
import threading
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from starlette.requests import Request
from pydantic import BaseModel
from typing import Optional

import database as db
import scanner
import tag_writer
import paths

app = FastAPI(title="Tagicus", version="0.1.0")

# Initialize database on startup
@app.on_event("startup")
def startup():
    db.init_db()

# --- API Models ---

class FieldUpdate(BaseModel):
    value: str

class ScanRequest(BaseModel):
    path: str
    full_rescan: bool = False

class ApplyRequest(BaseModel):
    organize: bool = True
    base_path: Optional[str] = None

class LibraryCreate(BaseModel):
    name: str
    path: str

# --- Scan state ---
scan_status = {"running": False, "total": 0, "scanned": 0, "current": "", "cancel": False}

# --- Apply-batch state ---
apply_status = {"running": False, "total": 0, "applied": 0, "current": "", "errors": [], "cancel": False}

# --- Library Routes ---

@app.get("/api/libraries")
def get_libraries():
    return db.get_libraries()

@app.post("/api/libraries")
def add_library(lib: LibraryCreate):
    if not os.path.exists(lib.path):
        raise HTTPException(status_code=400, detail=f"Path not found: {lib.path}")
    lib_id = db.add_library(lib.name, lib.path)
    if lib_id is None:
        raise HTTPException(status_code=409, detail="Library with that path already exists")
    return {"id": lib_id, "name": lib.name, "path": lib.path}

@app.delete("/api/libraries/{lib_id}")
def delete_library(lib_id: int):
    lib = db.get_library(lib_id)
    if not lib:
        raise HTTPException(status_code=404, detail="Library not found")
    db.delete_library(lib_id)
    return {"deleted": True}

@app.delete("/api/songs/{song_id}")
def delete_song(song_id: int):
    song = db.get_song(song_id)
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    filepath = song["filepath"]
    # Delete the actual file
    if os.path.exists(paths.long_path(filepath)):
        os.remove(paths.long_path(filepath))
        # Clean up empty folders (bounded to the song's library, if known)
        old_dir = os.path.dirname(filepath)
        import tag_writer
        lib = db.get_library(song["library_id"]) if song.get("library_id") else None
        tag_writer._cleanup_empty_dirs(old_dir, stop_dir=lib["path"] if lib else None)
    # Remove from database
    d = db.get_db()
    d.execute("DELETE FROM song_votes WHERE song_id = ?", (song_id,))
    d.execute("DELETE FROM song_fields WHERE song_id = ?", (song_id,))
    d.execute("DELETE FROM songs WHERE id = ?", (song_id,))
    d.commit()
    d.close()
    return {"deleted": True}

# --- API Routes ---

@app.get("/api/duplicates")
def get_duplicates():
    return db.find_duplicates()

@app.get("/api/stats")
def get_stats():
    stats = db.get_stats()
    stats["scan_running"] = scan_status["running"]
    stats["scan_progress"] = scan_status
    stats["apply_running"] = apply_status["running"]
    stats["apply_progress"] = apply_status
    return stats

@app.get("/api/songs")
def get_songs(status: Optional[str] = None):
    return db.get_all_songs(status)

@app.get("/api/songs/{song_id}")
def get_song(song_id: int):
    song = db.get_song(song_id)
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    return song

@app.put("/api/songs/{song_id}/fields/{field_name}")
def update_field(song_id: int, field_name: str, update: FieldUpdate):
    valid = ["artist", "title", "album", "year", "track", "genre"]
    if field_name not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid field: {field_name}")
    db.update_field(song_id, field_name, update.value)
    return db.get_song(song_id)

@app.post("/api/songs/{song_id}/rescan")
def rescan_song(song_id: int):
    result = scanner.rescan_file(song_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Song not found or file missing")
    return db.get_song(song_id)

@app.post("/api/songs/{song_id}/apply")
def apply_song_tags(song_id: int, req: ApplyRequest = ApplyRequest()):
    result = tag_writer.apply_tags(song_id, organize=req.organize, base_path=req.base_path)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/api/apply-batch")
def apply_batch(req: ApplyRequest, bg: BackgroundTasks):
    if apply_status["running"]:
        raise HTTPException(status_code=409, detail="Apply already in progress")

    songs = db.get_all_songs("ready")
    apply_status.update({"running": True, "total": len(songs), "applied": 0, "current": "", "errors": [], "cancel": False})
    bg.add_task(_run_apply_batch, songs, req.organize, req.base_path)
    return {"message": "Apply started", "total": len(songs)}

@app.get("/api/apply-batch/status")
def get_apply_status():
    return apply_status

@app.post("/api/apply-batch/cancel")
def cancel_apply_batch():
    if not apply_status["running"]:
        return {"message": "No apply in progress"}
    apply_status["cancel"] = True
    return {"message": "Cancelling apply"}

def _run_apply_batch(songs, organize, base_path):
    for song in songs:
        if apply_status["cancel"]:
            break
        apply_status["current"] = song["filename"]
        result = tag_writer.apply_tags(song["id"], organize=organize, base_path=base_path)
        if "error" in result:
            apply_status["errors"].append({"id": song["id"], "file": song["filename"], "error": result["error"]})
        apply_status["applied"] += 1
    apply_status["running"] = False
    apply_status["current"] = ""
    apply_status["cancel"] = False

@app.post("/api/approve-reviews")
def approve_reviews():
    """Move all 'review' songs to 'ready' (approved) status."""
    d = db.get_db()
    count = d.execute("SELECT COUNT(*) as c FROM songs WHERE status = 'review'").fetchone()["c"]
    d.execute("UPDATE songs SET status = 'ready', updated_at = datetime('now') WHERE status = 'review'")
    d.commit()
    d.close()
    return {"approved": count}

@app.post("/api/scan")
def start_scan(req: ScanRequest, bg: BackgroundTasks):
    if scan_status["running"]:
        raise HTTPException(status_code=409, detail="Scan already in progress")

    if not os.path.exists(req.path):
        raise HTTPException(status_code=400, detail=f"Path not found: {req.path}")

    scan_status["full_rescan"] = req.full_rescan
    bg.add_task(_run_scan, req.path)
    return {"message": "Scan started", "path": req.path}

@app.get("/api/scan/status")
def get_scan_status():
    return scan_status

@app.post("/api/scan/cancel")
def cancel_scan():
    if not scan_status["running"]:
        return {"message": "No scan running"}
    scan_status["cancel"] = True
    return {"message": "Cancelling scan"}

@app.get("/api/audio/{song_id}")
def stream_audio(song_id: int, request: Request):
    song = db.get_song(song_id)
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    filepath = song["filepath"]
    safe_filepath = paths.long_path(filepath)
    if not os.path.exists(safe_filepath):
        raise HTTPException(status_code=404, detail="File not found")

    ext = os.path.splitext(filepath)[1].lower()
    media_types = {
        ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".aac": "audio/aac",
        ".flac": "audio/flac", ".ogg": "audio/ogg", ".opus": "audio/opus",
        ".wav": "audio/wav", ".ape": "audio/x-ape",
    }
    mt = media_types.get(ext, "audio/mpeg")
    file_size = os.path.getsize(safe_filepath)

    range_header = request.headers.get("range")

    if range_header:
        range_val = range_header.strip().split("=")[1]
        start, end = range_val.split("-")
        start = int(start)
        end = int(end) if end else file_size - 1
        length = end - start + 1

        def iter_range():
            with open(safe_filepath, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk_size = min(65536, remaining)
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingResponse(
            iter_range(),
            status_code=206,
            media_type=mt,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Content-Length": str(length),
                "Accept-Ranges": "bytes",
            }
        )
    else:
        def iter_file():
            with open(safe_filepath, "rb") as f:
                while chunk := f.read(65536):
                    yield chunk

        return StreamingResponse(
            iter_file(),
            media_type=mt,
            headers={
                "Content-Length": str(file_size),
                "Accept-Ranges": "bytes",
            }
        )



def _run_scan(path):
    import glob
    scan_status["running"] = True
    db.cleanup_missing_files()
    scan_status["scanned"] = 0

    config = scanner.load_config()
    config["_full_rescan"] = scan_status.get("full_rescan", False)

    audio_files = []
    exts = ["mp3", "m4a", "flac", "ogg", "ape", "wma", "wav", "aac", "opus"]
    if os.path.isfile(path):
        audio_files = [path]
    else:
        for ext in exts:
            audio_files.extend(glob.glob(os.path.join(path, "**", f"*.{ext}"), recursive=True))
            audio_files.extend(glob.glob(os.path.join(path, "**", f"*.{ext.upper()}"), recursive=True))
    audio_files = sorted(set(audio_files))
    scan_status["total"] = len(audio_files)

    import time
    for i, fp in enumerate(audio_files):
        scan_status["current"] = os.path.basename(fp)
        try:
            scanner.scan_file(fp, config)
        except Exception as e:
            pass  # Log error but continue scanning
        scan_status["scanned"] = i + 1
        if scan_status["cancel"]:
            break
        if i < len(audio_files) - 1:
            time.sleep(1)

    scan_status["running"] = False
    scan_status["current"] = ""
    scan_status["cancel"] = False


# --- Serve Frontend ---

app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    index_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(index_path):
        with open(index_path) as f:
            return f.read()
    return HTMLResponse("<h1>Tagicus</h1><p>Frontend not found. Place index.html in app/static/</p>")

# --- ADDED ENDPOINTS ---

@app.get("/api/settings")
def get_settings():
    return db.get_all_settings()


@app.put("/api/settings")
def update_settings(updates: dict):
    valid_keys = set(db.DEFAULTS.keys())
    filtered = {k: v for k, v in updates.items() if k in valid_keys}
    db.set_settings(filtered)
    return db.get_all_settings()


@app.get("/api/settings/filename-preview")
def filename_preview():
    """Generate a sample filename preview using current settings."""
    settings = db.get_all_settings()
    folder_pattern = settings.get("folder_pattern", "{artist}/{album} ({year})")
    file_pattern = settings.get("file_pattern", "{track} - {artist} - {title}")

    sample = {
        "artist": "Frank Sinatra",
        "title": "My Way",
        "album": "My Way",
        "year": "1969",
        "track": "01",
        "genre": "Jazz",
    }

    try:
        folder = folder_pattern.format(**sample)
        filename = file_pattern.format(**sample) + ".mp3"
        return {"preview": f"{folder}/{filename}"}
    except KeyError as e:
        return {"preview": f"Invalid pattern: unknown tag {e}"}

@app.post("/api/cleanup")
def cleanup():
    removed = db.cleanup_missing_files()
    return {"removed": removed}

