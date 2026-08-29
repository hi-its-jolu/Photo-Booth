import http.server
import threading
import socket
import os

_PORT = 8080
_server: http.server.HTTPServer | None = None


def get_local_ip() -> str:
    """Return the machine's LAN IP (no internet needed), or 127.0.0.1 as fallback."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.254.254.254', 1))
        return s.getsockname()[0]
    except Exception:
        return '127.0.0.1'
    finally:
        s.close()


def start_file_server(directory: str, port: int = _PORT) -> str:
    """Serve `directory` over HTTP in a daemon thread. Returns the base URL."""
    global _server
    os.makedirs(directory, exist_ok=True)

    class _Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=directory, **kwargs)

        def log_message(self, *args):
            pass  # silence access logs

    _server = http.server.HTTPServer(('', port), _Handler)
    threading.Thread(target=_server.serve_forever, daemon=True).start()
    ip = get_local_ip()
    print(f"Photo server: http://{ip}:{port}/")
    return f"http://{ip}:{port}"
