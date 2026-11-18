"""
backend/api/router.py
FastAPI Application: API Endpoints for analysis progress/results and static asset mounting.
"""

import os
import shutil
import tempfile
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.analysis.pipeline import run_pipeline
from backend.models import SongTimeline, APP_VERSION
from backend.utils.midi_export import export_arrangement_to_midi_bytes
from backend.utils.library_store import library_store

app = FastAPI(title="HotChords API", version=APP_VERSION)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_progress = {"msg": "Waiting...", "pct": 0}
_result = {"ready": False, "data": None, "error": None}
_analyzing = False

def upd_callback(msg, pct):
    global _progress
    _progress["msg"] = msg
    _progress["pct"] = pct
    print(f"  [{pct:3d}%] {msg}")

def run_analysis_task(temp_path: str, filename: str, cleanup: bool = False, quality_mode: str = "balanced"):
    global _result, _analyzing, _progress
    _analyzing = True
    _result.update({"ready": False, "data": None, "error": None})
    _progress.update({"msg": "Starting...", "pct": 0})
    
    try:
        # Check if an identical audio file already exists in the 10-song library
        audio_hash = library_store.compute_file_hash(temp_path) if os.path.isfile(temp_path) else ""
        cached_entry = library_store.find_by_hash(audio_hash)
        if cached_entry:
            upd_callback("Restoring saved piano arrangement from Library...", 95)
            cached_data = library_store.load_song_data(audio_hash)
            if cached_data:
                cached_data["file"] = filename
                _result["data"] = cached_data
                _result["error"] = None
                _result["ready"] = True
                upd_callback("Done!", 100)
                return

        raw_analysis = run_pipeline(temp_path, upd_callback=upd_callback, quality_mode=quality_mode)
        raw_analysis["file"] = filename
        
        # Convert analysis result into canonical SongTimeline
        timeline = SongTimeline.from_analysis_dict(raw_analysis)
        
        # Build backwards-compatible legacy dictionary for current frontend
        data = timeline.to_analysis_dict()
        data["file"] = filename
        data["timeline"] = timeline.model_dump(by_alias=True)
        if "_stem_paths" in raw_analysis:
            data["_stem_paths"] = raw_analysis["_stem_paths"]

        # Automatically save into the 10-song Library
        try:
            saved_meta = library_store.save_completed_song(
                audio_path=temp_path,
                original_filename=filename,
                analysis_data=data,
                song_id=audio_hash or None,
            )
            loaded = library_store.load_song_data(saved_meta["id"])
            if loaded:
                data = loaded
        except Exception as lib_err:
            print(f"[Library] Warning saving song: {lib_err}")
        
        _result["data"] = data
        _result["error"] = None
        _result["ready"] = True
    except Exception as e:
        import traceback
        traceback.print_exc()
        _result["error"] = str(e)
        _result["ready"] = True
    finally:
        _analyzing = False
        if cleanup:
            try:
                os.unlink(temp_path)
            except:
                pass

@app.get("/health")
def get_health():
    return {"status": "ready"}


@app.get("/engines/status")
def get_engines_status():
    """Return read-only availability of transcription, separation, and chord engines."""
    from backend.analysis.engines import BasicPitchEngine
    from backend.analysis.source_separation import HTDemucsSeparationEngine, RoFormerSeparationEngine
    from backend.analysis.lv_chordia_engine import LVChordiaEngine

    bp_ok, bp_reason = BasicPitchEngine().check_availability()
    ht_ok, ht_reason = HTDemucsSeparationEngine().check_availability()
    rf_ok, rf_reason = RoFormerSeparationEngine().check_availability()
    lv_ok, lv_reason = LVChordiaEngine().check_availability()

    return {
        "quality_modes": ["fast", "balanced", "high_accuracy"],
        "engines": {
            "hotchords_native": {"available": True, "reason": None},
            "basic_pitch_onnx": {"available": bp_ok, "reason": bp_reason},
            "htdemucs": {"available": ht_ok, "reason": ht_reason},
            "roformer": {"available": rf_ok, "reason": rf_reason},
            "lv_chordia": {"available": lv_ok, "reason": lv_reason},
        },
    }

@app.get("/progress")
def get_progress():
    return _progress

@app.get("/result")
def get_result():
    if _result["ready"]:
        if _result["error"]:
            return JSONResponse(status_code=200, content={"ready": True, "error": _result["error"]})
        if _result["data"]:
            data = dict(_result["data"])
            data["ready"] = True
            data["error"] = None
            return data
        return JSONResponse(status_code=200, content={"ready": True, "error": "No data generated"})
    return JSONResponse(status_code=200, content={"ready": False})

@app.get("/timeline")
def get_timeline():
    if _result["ready"]:
        if _result["error"]:
            return JSONResponse(status_code=500, content={"error": _result["error"]})
        if _result["data"] and "timeline" in _result["data"]:
            return _result["data"]["timeline"]
        return JSONResponse(status_code=404, content={"error": "Timeline not found"})
    return JSONResponse(status_code=202, content={"ready": False})


@app.get("/stems/{stem_name}")
def get_stem_audio(stem_name: str, download: bool = False):
    if not _result["ready"] or not _result["data"]:
        raise HTTPException(status_code=404, detail="No active song analysis")
    stem_paths = _result["data"].get("_stem_paths", {})
    fpath = stem_paths.get(stem_name)
    if (not fpath or not os.path.isfile(fpath)) and _result["data"].get("song_id"):
        fpath = library_store.get_stem_path(_result["data"]["song_id"], stem_name)
    if not fpath or not os.path.isfile(fpath):
        raise HTTPException(status_code=404, detail=f"Stem '{stem_name}' not available")
    title = os.path.splitext(os.path.basename(_result["data"].get("file", "song")))[0]
    dl_name = f"{title}_{stem_name}.wav" if download else f"{stem_name}.wav"
    headers = {"Content-Disposition": f'attachment; filename="{dl_name}"'} if download else {}
    return FileResponse(fpath, media_type="audio/wav", filename=dl_name, headers=headers)


# ══════════════════════════════════════════════════════════════
#  SONG LIBRARY ENDPOINTS (Latest 10 Completed Songs)
# ══════════════════════════════════════════════════════════════
@app.get("/library")
def list_library_songs():
    return {
        "songs": library_store.list_songs(),
        "folders": library_store.list_folders(),
    }


@app.get("/library/folders")
def list_library_folders():
    return {"folders": library_store.list_folders()}


@app.post("/library/folders")
def create_library_folder(payload: dict):
    name = str((payload or {}).get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Folder name is required")
    return {"folders": library_store.create_folder(name)}


@app.delete("/library/folders/{folder_name}")
def delete_library_folder(folder_name: str):
    return {"folders": library_store.delete_folder(folder_name)}


@app.patch("/library/{song_id}")
def update_library_song(song_id: str, payload: dict):
    title = (payload or {}).get("title")
    folder = (payload or {}).get("folder")
    updated = library_store.update_song_metadata(song_id, title=title, folder=folder)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Song '{song_id}' not found")
    return {"song": updated, "folders": library_store.list_folders()}


@app.post("/library/{song_id}/open")
def open_library_song(song_id: str):
    global _result, _progress
    data = library_store.load_song_data(song_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Song '{song_id}' not found in library")
    library_store.touch_last_accessed(song_id)
    entry = next((s for s in library_store.list_songs() if s.get("id") == song_id), None)
    if entry and entry.get("title"):
        data["title"] = entry["title"]
        data["folder"] = entry.get("folder", "Unsorted")
    data["ready"] = True
    data["error"] = None
    data["audio_url"] = f"/library/{song_id}/audio"
    _result["data"] = data
    _result["error"] = None
    _result["ready"] = True
    _progress = {"msg": "Done!", "pct": 100}
    return data


@app.post("/library/{song_id}/extract-stems")
def extract_library_song_stems(song_id: str):
    global _result
    try:
        stem_info = library_store.extract_stems_for_song(song_id, progress_cb=upd_callback)
        if _result.get("data") and _result["data"].get("song_id") == song_id:
            updated = library_store.load_song_data(song_id)
            if updated:
                updated["ready"] = True
                _result["data"] = updated
        return {"status": "ready", "stems": stem_info}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stem extraction failed: {e}")


@app.delete("/library/{song_id}")
def delete_library_song(song_id: str):
    removed = library_store.delete_song(song_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Song '{song_id}' not found")
    return {"status": "deleted", "id": song_id}


@app.get("/library/{song_id}/audio")
def get_library_song_audio(song_id: str):
    apath = library_store.get_audio_path(song_id)
    if not apath or not os.path.isfile(apath):
        raise HTTPException(status_code=404, detail="Audio file not found for this song")
    return FileResponse(apath, filename=os.path.basename(apath))


@app.get("/library/{song_id}/stems/{stem_name}")
def get_library_song_stem(song_id: str, stem_name: str, download: bool = False):
    spath = library_store.get_stem_path(song_id, stem_name)
    if not spath or not os.path.isfile(spath):
        raise HTTPException(status_code=404, detail=f"Stem '{stem_name}' not available for song '{song_id}'")
    data = library_store.load_song_data(song_id) or {}
    title = os.path.splitext(os.path.basename(data.get("file", song_id)))[0]
    norm = "vocals" if stem_name == "vocals" else "instrumental"
    dl_name = f"{title}_{norm}.wav"
    headers = {"Content-Disposition": f'attachment; filename="{dl_name}"'} if download else {}
    return FileResponse(spath, media_type="audio/wav", filename=dl_name, headers=headers)


@app.get("/export/midi")
def export_midi(mode: str = "original"):
    if not _result["ready"] or not _result["data"]:
        raise HTTPException(status_code=404, detail="No active song analysis")
    data = _result["data"]
    is_beg = str(mode).lower() in ("simplified", "beginner", "simple")
    notes = data.get("beginner_notes") if is_beg else data.get("notes")
    chords = data.get("beginner_chords") if is_beg else data.get("chords")
    tempo = float(data.get("tempo", 120.0))
    time_sig = str(data.get("time_sig", "4/4"))
    title = str(data.get("file", "HotChords_Arrangement"))

    midi_bytes = export_arrangement_to_midi_bytes(
        notes=notes or [],
        chords=chords or [],
        tempo=tempo,
        time_sig=time_sig,
        title=title,
    )
    safe_name = os.path.splitext(os.path.basename(title))[0] or "arrangement"
    out_filename = f"{safe_name}_{'beginner' if is_beg else 'intermediate'}.mid"
    return Response(
        content=midi_bytes,
        media_type="audio/midi",
        headers={"Content-Disposition": f'attachment; filename="{out_filename}"'},
    )


@app.post("/analyze-path")
def analyze_path(payload: dict, background_tasks: BackgroundTasks):
    global _result, _progress, _analyzing
    fpath = payload.get("path", "")
    quality_mode = str(payload.get("quality_mode") or "balanced")
    if not os.path.isfile(fpath):
        raise HTTPException(status_code=400, detail=f"File not found: {fpath}")
    
    _result = {"ready": False, "data": None, "error": None}
    _progress = {"msg": "Starting...", "pct": 1}
    _analyzing = True
    background_tasks.add_task(run_analysis_task, fpath, os.path.basename(fpath), False, quality_mode)
    return {"status": "started", "quality_mode": quality_mode}

@app.post("/analyze")
def analyze_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    quality_mode: str = Form("balanced"),
):
    global _result, _progress, _analyzing
    _result = {"ready": False, "data": None, "error": None}
    _progress = {"msg": "Saving uploaded audio file...", "pct": 5}
    _analyzing = True

    suffix = os.path.splitext(file.filename)[1] if file.filename else '.tmp'
    
    # Save UploadFile to a named temporary file
    temp_fd, temp_path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(temp_fd, 'wb') as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        os.close(temp_fd)
        try:
            os.unlink(temp_path)
        except:
            pass
        _result = {"ready": True, "data": None, "error": f"Could not save uploaded file: {e}"}
        _progress = {"msg": "Upload failed", "pct": 0}
        _analyzing = False
        raise HTTPException(status_code=500, detail=f"Could not save uploaded file: {e}")
        
    _progress.update({"msg": "File received, starting analysis...", "pct": 10})
    background_tasks.add_task(run_analysis_task, temp_path, file.filename, True, quality_mode)
    return {"status": "started", "quality_mode": quality_mode}

# ══════════════════════════════════════════════════════════════
#  STATIC FILES MOUNTING
# ══════════════════════════════════════════════════════════════
# Mount static assets (CSS, JS)
def _get_frontend_dir() -> str:
    import sys
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            bundle_dir = os.path.join(sys._MEIPASS, "frontend")
            if os.path.isdir(bundle_dir):
                return os.path.abspath(bundle_dir)
        exe_dir = os.path.join(os.path.dirname(sys.executable), "frontend")
        if os.path.isdir(exe_dir):
            return os.path.abspath(exe_dir)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))

frontend_dir = _get_frontend_dir()

app.mount("/css", StaticFiles(directory=os.path.join(frontend_dir, "css")), name="css")
app.mount("/js", StaticFiles(directory=os.path.join(frontend_dir, "js")), name="js")
app.mount("/audio", StaticFiles(directory=os.path.join(frontend_dir, "audio")), name="audio")


@app.get("/")
def get_index():
    return FileResponse(os.path.join(frontend_dir, "index.html"))

@app.get("/index.html")
def get_index_html():
    return FileResponse(os.path.join(frontend_dir, "index.html"))
