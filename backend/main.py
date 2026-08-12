"""
backend/main.py
Main entrypoint for HotChords. Starts the Uvicorn server and automatically opens the browser.
"""

import time
import threading
import webbrowser
import uvicorn

PORT = 5500

def open_browser():
    time.sleep(0.9)
    webbrowser.open(f"http://localhost:{PORT}")

if __name__ == '__main__':
    print('\n  HotChords : http://localhost:' + str(PORT))
    print('  Piano Chord Detection & Pedagogy Workstation')
    print('  Keep playing... developed by HotFix\n')
    
    # Start thread to open browser
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Start Uvicorn ASGI server
    uvicorn.run("backend.api.router:app", host="127.0.0.1", port=PORT, log_level="warning")
