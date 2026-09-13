"""
backend/main.py
Main entrypoint for HotChords. Starts the Uvicorn server and automatically opens the browser.
"""

import sys
import os
import time
import threading
import webbrowser
import socket
import urllib.request
import urllib.error

# Ensure workspace root is in sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import uvicorn
from backend.api.router import app

def get_free_port(start_port=5500):
    """Find a free port starting from the given port."""
    for port in range(start_port, start_port + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
    raise RuntimeError("No free ports available.")

PORT = get_free_port(5500)

def get_app_url(port: int = None) -> str:
    """Return the canonical HotChords application URL for a given port."""
    if port is None:
        port = PORT
    return f"http://hotchords.localhost:{port}"

def print_ready_banner(port: int = None):
    """Print the standardized ready banner containing the dynamic application URL."""
    if port is None:
        port = PORT
    url = get_app_url(port)
    banner = (
        "\n═══════════════════════════════════════════════════════════════\n"
        "  HotChords is ready.\n\n"
        "  Open HotChords:\n"
        f"  {url}\n\n"
        "  If HotChords did not open automatically, click the link above\n"
        "  or copy/type the address into your browser.\n"
        "═══════════════════════════════════════════════════════════════\n"
    )
    print(banner, flush=True)

def open_browser(port: int = None):
    """Poll the server until it responds, then open the browser and show ready message."""
    if port is None:
        port = PORT
    health_url = f"http://127.0.0.1:{port}/health"
    app_url = get_app_url(port)
    max_retries = 30
    for _ in range(max_retries):
        try:
            # Check if the server is responding
            with urllib.request.urlopen(health_url, timeout=1.0) as resp:
                if resp.status == 200:
                    webbrowser.open(app_url)
                    
                    # On macOS desktop/GUI, trigger notification if available
                    if sys.platform == "darwin":
                        try:
                            import subprocess
                            msg = f"Open HotChords: {app_url}"
                            title = "HotChords is ready"
                            subprocess.run(
                                ["osascript", "-e", f'display notification "{msg}" with title "{title}"'],
                                capture_output=True,
                                check=False
                            )
                        except Exception:
                            pass
                    return
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.5)
    print(f"\nFailed to auto-open browser. Please manually navigate to {app_url}", flush=True)

if __name__ == '__main__':
    print_ready_banner(PORT)
    
    # Start thread to open browser
    threading.Thread(target=open_browser, args=(PORT,), daemon=True).start()
    
    # Start Uvicorn ASGI server
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="info")
