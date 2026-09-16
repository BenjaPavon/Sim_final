"""Servidor web sin dependencias externas para la simulación de colas."""

from __future__ import annotations

import argparse
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from simulation import SimulationConfig, simulate_both


ROOT = Path(__file__).resolve().parent
STATIC_ROOT = (ROOT / "static").resolve()


class SimulationHandler(BaseHTTPRequestHandler):
    server_version = "SimulacionColas/1.0"

    def _send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path):
        try:
            body = path.read_bytes()
        except FileNotFoundError:
            self.send_error(HTTPStatus.NOT_FOUND, "Archivo no encontrado")
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8" if content_type.startswith("text/") else content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Allow", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        route = urlparse(self.path).path
        if route == "/api/defaults":
            self._send_json({"config": SimulationConfig().__dict__})
            return
        if route in {"", "/"}:
            self._send_file(STATIC_ROOT / "index.html")
            return
        requested = (STATIC_ROOT / unquote(route.lstrip("/"))).resolve()
        if requested != STATIC_ROOT and STATIC_ROOT not in requested.parents:
            self.send_error(HTTPStatus.FORBIDDEN, "Ruta no permitida")
            return
        self._send_file(requested)

    def do_POST(self):
        route = urlparse(self.path).path
        if route != "/api/simulate":
            self.send_error(HTTPStatus.NOT_FOUND, "Endpoint no encontrado")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 1_000_000:
                raise ValueError("La solicitud es demasiado grande")
            raw = self.rfile.read(length) if length else b"{}"
            payload = json.loads(raw.decode("utf-8"))
            config = payload.get("config", payload)
            self._send_json(simulate_both(config))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # Respuesta controlada; el servidor sigue activo.
            self.log_error("Error de simulación: %s", exc)
            self._send_json(
                {"error": "No se pudo ejecutar la simulación"},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulación web del cruce sobre el río")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), SimulationHandler)
    print(f"Simulador disponible en http://{args.host}:{args.port}")
    print("Presione Ctrl+C para detenerlo.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
