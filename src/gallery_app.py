import os
import threading

from flask import Flask, abort, jsonify, render_template, send_from_directory

from gallery_sessions import list_sessions, find_session, total_photo_count, flatten
from server import get_local_ip

_FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "fonts")


def create_app(photos_dir: str, prints_dir: str) -> Flask:
    app = Flask(__name__)

    @app.route("/")
    def index():
        sessions = list_sessions(photos_dir, prints_dir)
        return render_template("gallery_index.html", sessions=sessions, count=total_photo_count(sessions))

    @app.route("/photo/<sid>/<int:local_index>")
    def photo(sid, local_index):
        sessions = list_sessions(photos_dir, prints_dir)
        session = find_session(sessions, sid)
        if session is None or not (1 <= local_index <= len(session["photos"])):
            abort(404)

        order = flatten(sessions)
        pos = order.index((sid, local_index))
        prev_ref = order[pos - 1] if pos > 0 else None
        next_ref = order[pos + 1] if pos < len(order) - 1 else None

        return render_template(
            "gallery_photo.html",
            session=session,
            local_index=local_index,
            global_index=pos + 1,
            total=len(order),
            prev_ref=prev_ref,
            next_ref=next_ref,
        )

    @app.route("/photos/<path:filename>")
    def serve_photo(filename):
        return send_from_directory(photos_dir, filename)

    @app.route("/prints/<path:filename>")
    def serve_print(filename):
        return send_from_directory(prints_dir, filename)

    @app.route("/download/photos/<path:filename>")
    def download_photo(filename):
        return send_from_directory(photos_dir, filename, as_attachment=True)

    @app.route("/download/prints/<path:filename>")
    def download_print(filename):
        return send_from_directory(prints_dir, filename, as_attachment=True)

    @app.route("/fonts/<path:filename>")
    def serve_font(filename):
        return send_from_directory(_FONTS_DIR, filename)

    @app.route("/api/status")
    def status():
        return jsonify(count=total_photo_count(list_sessions(photos_dir, prints_dir)))

    return app


def start_gallery_server(photos_dir: str, prints_dir: str, port: int) -> str:
    """Serve the event gallery (Flask) in a daemon thread. Returns the base URL."""
    app = create_app(photos_dir, prints_dir)
    thread = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False, threaded=True),
        daemon=True,
    )
    thread.start()
    ip = get_local_ip()
    print(f"Gallery: http://{ip}:{port}/")
    return f"http://{ip}:{port}"
