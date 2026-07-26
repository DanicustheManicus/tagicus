"""
Tagicus - Desktop Launcher

Starts the FastAPI backend in a background thread on a local port and
opens it in a native OS window via pywebview (no browser tab).
"""

import os
import sys
import socket
import threading
import time
import urllib.request
import urllib.error

import webview


def _base_dir():
    """Directory containing server.py, database.py, static/, etc."""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "app")


def _fpcalc_path():
    plat = "windows" if sys.platform == "win32" else "linux"
    name = "fpcalc.exe" if plat == "windows" else "fpcalc"
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, name)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor", "fpcalc", plat, name)


def _icon_path():
    name = "icon.ico" if sys.platform == "win32" else "icon.png"
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, name)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", name)


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _run_server(port):
    import uvicorn
    import server
    uvicorn.run(server.app, host="127.0.0.1", port=port, log_level="warning")


def _wait_for_server(port, timeout=10):
    deadline = time.time() + timeout
    url = f"http://127.0.0.1:{port}/api/stats"
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=0.5)
            return True
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.1)
    return False


class Api:
    def choose_folder(self):
        result = webview.windows[0].create_file_dialog(webview.FileDialog.FOLDER)
        return result[0] if result else None


def main():
    os.environ["FPCALC"] = _fpcalc_path()
    sys.path.insert(0, _base_dir())

    import paths
    webview_storage_path = os.path.join(paths.get_data_dir(), "webview")

    port = _free_port()
    threading.Thread(target=_run_server, args=(port,), daemon=True).start()
    _wait_for_server(port)

    webview.create_window(
        "Tagicus",
        f"http://127.0.0.1:{port}",
        js_api=Api(),
        width=1280,
        height=860,
        min_size=(900, 600),
    )
    webview.start(icon=_icon_path(), private_mode=False, storage_path=webview_storage_path)


if __name__ == "__main__":
    main()
