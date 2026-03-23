from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .config import default_config_path, load_config, load_dotenv
from .dashboard import DashboardService


def _asset_bytes(name: str) -> bytes:
    return files("fitech_agent.web").joinpath(name).read_bytes()


class DashboardRequestHandler(BaseHTTPRequestHandler):
    service: DashboardService
    assets: dict[str, tuple[bytes, str]]

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path == "/":
            self._write_bytes(HTTPStatus.OK, *self.assets["/"])
            return
        if path in self.assets:
            self._write_bytes(HTTPStatus.OK, *self.assets[path])
            return
        if path == "/api/bootstrap":
            self._write_json(HTTPStatus.OK, self.service.bootstrap_payload())
            return
        if path == "/api/report-file":
            try:
                raw_path = query.get("path", [""])[0]
                file_path, content_type = self.service.resolve_report_file(raw_path)
                body = file_path.read_bytes()
                self.send_response(HTTPStatus.OK.value)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header(
                    "Content-Disposition",
                    f'inline; filename="{file_path.name}"',
                )
                self.end_headers()
                self.wfile.write(body)
            except ValueError as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        self._write_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            payload = self._read_json_body()
            if path == "/api/research/run":
                self._write_json(HTTPStatus.OK, self.service.run_research(payload))
                return
            if path == "/api/research/chat":
                self._write_json(HTTPStatus.OK, self.service.answer_question(payload))
                return
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        except ValueError as exc:
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:
            self._write_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    def log_message(self, format: str, *args: object) -> None:
        return

    def _read_json_body(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            return {}
        raw = self.rfile.read(content_length)
        if not raw:
            return {}
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("invalid JSON body") from exc
        if not isinstance(parsed, dict):
            raise ValueError("JSON body must be an object")
        return parsed

    def _write_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._write_bytes(status, body, "application/json; charset=utf-8")

    def _write_bytes(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(status.value)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _build_handler(service: DashboardService) -> type[DashboardRequestHandler]:
    assets = {
        "/": (_asset_bytes("index.html"), "text/html; charset=utf-8"),
        "/static/app.css": (_asset_bytes("app.css"), "text/css; charset=utf-8"),
        "/static/app.js": (_asset_bytes("app.js"), "application/javascript; charset=utf-8"),
    }
    return type(
        "ConfiguredDashboardRequestHandler",
        (DashboardRequestHandler,),
        {
            "service": service,
            "assets": assets,
        },
    )


def create_server(
    *,
    config_path: str | Path | None = None,
    host: str = "127.0.0.1",
    port: int = 8010,
) -> ThreadingHTTPServer:
    load_dotenv()
    resolved = (
        Path(config_path)
        if config_path is not None
        else default_config_path()
    )
    config = load_config(resolved if resolved and resolved.exists() else None)
    service = DashboardService(config)
    server = ThreadingHTTPServer((host, port), _build_handler(service))
    return server
