"""
HotChords Entry Point
Delegates execution to the modularized FastAPI/Uvicorn backend.
"""

import sys
import os

# Ensure the root project directory is in the Python search path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Dynamically inject bundled FFmpeg into the system PATH if available.
# This prevents Windows users from having to manually install FFmpeg.
try:
    import imageio_ffmpeg
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    ffmpeg_dir = os.path.dirname(ffmpeg_exe)
    os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
except ImportError:
    pass

if __name__ == "__main__":
    from backend.main import run_server
    run_server("backend.api.router:app", log_level="warning")
