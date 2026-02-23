"""
ui/server.py

Lightweight Flask server with Server-Sent Events (SSE).
The orchestrator pushes events here; the browser dashboard subscribes
via EventSource and updates in real time — no WebSocket complexity needed.
"""

import json
import queue
import threading
import webbrowser
import time
from flask import Flask, Response, send_from_directory
import os

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), "static"))

# Thread-safe event queue — orchestrator writes, SSE endpoint reads
_event_queue: queue.Queue = queue.Queue(maxsize=500)

# Store full session history so late-joining browser gets full picture
_session_history: list = []
_history_lock = threading.Lock()


# ------------------------------------------------------------------ #
#  Event push (called by orchestrator)                               #
# ------------------------------------------------------------------ #

def push_event(event_type: str, data: dict):
    """Push an event from the simulation thread into the SSE stream."""
    payload = {"type": event_type, "data": data}
    with _history_lock:
        _session_history.append(payload)
    try:
        _event_queue.put_nowait(payload)
    except queue.Full:
        pass  # drop if queue overflows


# ------------------------------------------------------------------ #
#  Routes                                                             #
# ------------------------------------------------------------------ #

@app.route("/")
def index():
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    return send_from_directory(static_dir, "index.html")


@app.route("/history")
def history():
    """Return full session history for late-joining clients."""
    with _history_lock:
        return Response(
            json.dumps(_session_history),
            mimetype="application/json"
        )


@app.route("/stream")
def stream():
    """SSE endpoint — browser connects here and receives live events."""
    def generate():
        # First, replay history so the page loads with existing data
        with _history_lock:
            for payload in _session_history:
                yield f"data: {json.dumps(payload)}\n\n"

        # Then stream new events
        while True:
            try:
                payload = _event_queue.get(timeout=30)
                yield f"data: {json.dumps(payload)}\n\n"
            except queue.Empty:
                yield ": heartbeat\n\n"   # keep connection alive

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


# ------------------------------------------------------------------ #
#  Server lifecycle                                                   #
# ------------------------------------------------------------------ #

def start(port: int = 5000, open_browser: bool = True):
    """Start Flask in a daemon thread so it doesn't block the simulation."""
    def _run():
        import logging
        log = logging.getLogger("werkzeug")
        log.setLevel(logging.ERROR)   # silence Flask request logs
        app.run(port=port, threaded=True, use_reloader=False)

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    # Give Flask a moment to bind
    time.sleep(1.0)

    if open_browser:
        webbrowser.open(f"http://localhost:{port}")

    return port