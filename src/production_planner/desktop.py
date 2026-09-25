from __future__ import annotations

import socket
import sys
import threading
import time
from pathlib import Path

import uvicorn

from .api import create_app
from .errors import ValidationError


def resource_root() -> Path:
    bundled = getattr(sys, "_MEIPASS", None)
    return Path(bundled) if bundled else Path(__file__).resolve().parents[2]


def bundled_database_path() -> Path:
    return resource_root() / "sampledata" / "hay_day.sqlite"


def _available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def run_desktop(database: Path | None = None, plan: Path | None = None, debug: bool = False) -> None:
    try:
        import webview
    except ImportError as exc:
        raise ValidationError("desktop support is not installed; run scripts/setup.ps1") from exc

    if database is None and plan is None:
        database = bundled_database_path()
    if database is not None and not database.is_file():
        raise ValidationError(f"desktop catalog does not exist: {database}")

    port = _available_port()
    server = uvicorn.Server(uvicorn.Config(
        create_app(database=database, plan=plan),
        host="127.0.0.1",
        port=port,
        log_level="warning",
    ))
    thread = threading.Thread(target=server.run, name="planner-local-server", daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.025)
    if not server.started:
        server.should_exit = True
        raise ValidationError("the local planner server did not start")

    webview.create_window(
        "Production Planner",
        f"http://127.0.0.1:{port}",
        width=1440,
        height=900,
        min_size=(960, 640),
        background_color="#F8FAF9",
    )
    try:
        webview.start(debug=debug)
    finally:
        server.should_exit = True
        thread.join(timeout=5)
