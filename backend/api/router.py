"""
backend/api/router.py
FastAPI Application: API Endpoints for analysis progress/results and static asset mounting.
"""

import os
import shutil
import tempfile
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.analysis.pipeline import run_pipeline

app = FastAPI(title="HotChords API")

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

def run_analysis_task(temp_path: str, filename: str, cleanup: bool = False):
    global _result, _analyzing, _progress
    _analyzing = True
    _result.update({"ready": False, "data": None, "error": None})
    _progress.update({"msg": "Starting...", "pct": 0})
    
    try:
        data = run_pipeline(temp_path, upd_callback=upd_callback)
        data["file"] = filename
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

@app.get("/progress")
def get_progress():
    return _progress

@app.get("/result")
def get_result():
    if _result["ready"]:
        if _result["error"]:
            return JSONResponse(status_code=500, content={"error": _result["error"]})
        return _result["data"]
    return JSONResponse(status_code=202, content={"ready": False})

@app.post("/analyze-path")
def analyze_path(payload: dict, background_tasks: BackgroundTasks):
    fpath = payload.get("path", "")
    if not os.path.isfile(fpath):
        raise HTTPException(status_code=400, detail=f"File not found: {fpath}")
    
    _progress.update({"msg": "Starting...", "pct": 1})
    background_tasks.add_task(run_analysis_task, fpath, os.path.basename(fpath), False)
    return {"status": "started"}

@app.post("/analyze")
def analyze_upload(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
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
        raise HTTPException(status_code=500, detail=f"Could not save uploaded file: {e}")
        
    _progress.update({"msg": "File received, analyzing...", "pct": 10})
    background_tasks.add_task(run_analysis_task, temp_path, file.filename, True)
    return {"status": "started"}

# ══════════════════════════════════════════════════════════════
#  STATIC FILES MOUNTING
# ══════════════════════════════════════════════════════════════
# Mount static assets (CSS, JS)
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))

app.mount("/css", StaticFiles(directory=os.path.join(frontend_dir, "css")), name="css")
app.mount("/js", StaticFiles(directory=os.path.join(frontend_dir, "js")), name="js")

@app.get("/")
def get_index():
    return FileResponse(os.path.join(frontend_dir, "index.html"))

@app.get("/index.html")
def get_index_html():
    return FileResponse(os.path.join(frontend_dir, "index.html"))
