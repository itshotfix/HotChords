"""
HotChords Entry Point
Delegates execution to the modularized FastAPI/Uvicorn backend.
"""

import sys
import os
import threading
import uvicorn

# Ensure the root project directory is in the Python search path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

if __name__ == '__main__':
    from backend.main import PORT, open_browser
    
    print('\n  HotChords : http://localhost:' + str(PORT))
    print('  Piano Chord Detection & Pedagogy Workstation')
    print('  Keep playing... developed by HotFix\n')
    
    # Start browser auto-launch thread
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Start Uvicorn ASGI server
    uvicorn.run("backend.api.router:app", host="127.0.0.1", port=PORT, log_level="warning")
