"""
backend/main.py
Main entrypoint for HotChords. Starts the Uvicorn server and automatically opens the browser.
"""

import time
import threading
import webbrowser
import uvicorn
import socket
import urllib.request
import urllib.error

def get_free_port(start_port=5500):
    """Find a free port starting from the given port."""
    for port in range(start_port, start_port + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
    raise RuntimeError("No free ports available.")

PORT = get_free_port(5500)

def open_browser():
    """Poll the server until it responds, then open the browser."""
    url = f"http://localhost:{PORT}"
    max_retries = 20
    for _ in range(max_retries):
        try:
            # Check if the server is responding
            urllib.request.urlopen(url)
            webbrowser.open(url)
            return
        except urllib.error.URLError:
            time.sleep(0.5)
    print(f"\\nFailed to auto-open browser. Please manually navigate to {url}")

if __name__ == '__main__':
    print('\n  HotChords : http://localhost:' + str(PORT))
    print('  Piano Chord Detection & Pedagogy Workstation')
    print('  Keep playing... developed by HotFix\n')
    
    # Start thread to open browser
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Start Uvicorn ASGI server
    uvicorn.run("backend.api.router:app", host="127.0.0.1", port=PORT, log_level="warning")
