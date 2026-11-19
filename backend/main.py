"""
backend/main.py
Main entrypoint and loopback port-allocation controller for HotChords.
"""

import sys
import os
import time
import json
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

LOOPBACK_HOST = "127.0.0.1"
DEFAULT_PORT_RANGE = 100


def get_preferred_port() -> int:
    """Return the configured preferred starting port (default 5500)."""
    raw = os.environ.get("HOTCHORDS_PORT") or os.environ.get("PORT") or "5500"
    try:
        port = int(raw)
        if 1024 <= port <= 65535:
            return port
    except ValueError:
        pass
    return 5500


def get_free_port(start_port: int = None, max_attempts: int = DEFAULT_PORT_RANGE) -> int:
    """Find an available loopback port by attempting a real bind on 127.0.0.1."""
    if start_port is None:
        start_port = get_preferred_port()
    for port in range(start_port, min(65536, start_port + max_attempts)):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                if os.name != "nt":
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                elif hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                s.bind((LOOPBACK_HOST, port))
                return port
            except OSError:
                continue
    raise RuntimeError(
        f"No free loopback ports available in range {start_port}-{min(65535, start_port + max_attempts - 1)}."
    )


def reserve_loopback_socket(
    start_port: int = None,
    max_attempts: int = DEFAULT_PORT_RANGE,
) -> tuple[int, socket.socket]:
    """
    Bind and keep a TCP socket open on 127.0.0.1 so Uvicorn can inherit it
    directly, preventing port-selection race conditions.
    """
    if start_port is None:
        start_port = get_preferred_port()
    last_err = None
    for port in range(start_port, min(65536, start_port + max_attempts)):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if os.name != "nt":
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            elif hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            sock.bind((LOOPBACK_HOST, port))
            sock.listen(128)
            sock.set_inheritable(True)
            return port, sock
        except OSError as exc:
            last_err = exc
            sock.close()
    raise RuntimeError(
        f"Could not bind any loopback port on {LOOPBACK_HOST} in range "
        f"{start_port}-{min(65535, start_port + max_attempts - 1)}: {last_err}"
    )


def find_running_hotchords_port(start_port: int = None, span: int = 10) -> int | None:
    """Return the port of an already-running HotChords instance, or None."""
    if start_port is None:
        start_port = get_preferred_port()
    for port in range(start_port, min(65536, start_port + span)):
        try:
            with urllib.request.urlopen(f"http://{LOOPBACK_HOST}:{port}/health", timeout=0.4) as resp:
                if resp.status != 200:
                    continue
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                if data.get("status") != "ready":
                    continue
            with urllib.request.urlopen(f"http://{LOOPBACK_HOST}:{port}/engines/status", timeout=2.0) as eresp:
                if eresp.status == 200 and b"hotchords_native" in eresp.read():
                    return port
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            continue
    return None


def get_app_url(port: int) -> str:
    """Return the canonical HotChords loopback application URL for a given port."""
    return f"http://{LOOPBACK_HOST}:{port}"


def print_ready_banner(port: int):
    """Print the standardized ready banner containing the dynamic application URL."""
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


def open_browser(port: int):
    """Poll /health on the selected port until ready, then open the browser."""
    health_url = f"http://{LOOPBACK_HOST}:{port}/health"
    app_url = get_app_url(port)
    for _ in range(40):
        try:
            with urllib.request.urlopen(health_url, timeout=1.0) as resp:
                if resp.status == 200:
                    webbrowser.open(app_url)
                    if sys.platform == "darwin":
                        try:
                            import subprocess
                            msg = f"Open HotChords: {app_url}"
                            title = "HotChords is ready"
                            subprocess.run(
                                ["osascript", "-e", f'display notification "{msg}" with title "{title}"'],
                                capture_output=True,
                                check=False,
                            )
                        except Exception:
                            pass
                    return
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.5)
    print(f"\nFailed to auto-open browser. Please manually navigate to {app_url}", flush=True)


def run_server(app_target=app, log_level: str = "info"):
    """
    Launch HotChords on a reserved loopback socket (127.0.0.1), or focus an
    already-running HotChords instance unless HOTCHORDS_ALLOW_MULTI=1.
    """
    allow_multi = os.environ.get("HOTCHORDS_ALLOW_MULTI", "0") == "1"
    if not allow_multi:
        existing_port = find_running_hotchords_port()
        if existing_port is not None:
            url = get_app_url(existing_port)
            print(f"\nHotChords is already running at {url}. Opening in browser...", flush=True)
            webbrowser.open(url)
            return

    port, bound_sock = reserve_loopback_socket()
    print_ready_banner(port)
    threading.Thread(target=open_browser, args=(port,), daemon=True).start()

    config = uvicorn.Config(app_target, host=LOOPBACK_HOST, port=port, log_level=log_level)
    server = uvicorn.Server(config)
    try:
        server.run(sockets=[bound_sock])
    finally:
        try:
            bound_sock.close()
        except OSError:
            pass


if __name__ == "__main__":
    run_server(app, log_level="info")
