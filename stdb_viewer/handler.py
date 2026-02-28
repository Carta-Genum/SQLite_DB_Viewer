"""
HTTP request handler.

Routes requests to API endpoints or serves the static frontend.
All database interaction goes through the Database class.
"""

import csv
import io
import json
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler
from pathlib import Path

from .database import DEFAULT_PAGE_SIZE

# Path to templates/static files
_PACKAGE_DIR = Path(__file__).parent


class ViewerHandler(BaseHTTPRequestHandler):
    """
    HTTP handler for the database viewer.

    Class-level attributes (injected before server starts):
        databases: dict[str, Database]
    """

    databases: dict  # set by main() before serving

    def log_message(self, fmt, *args):
        sys.stderr.write(f"[viewer] {args[0]}\n")

    # ---- Routing ----

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        routes = {
            "/":               lambda: self._serve_static("templates/index.html", "text/html"),
            "/static/css/style.css": lambda: self._serve_static("static/css/style.css", "text/css"),
            "/static/js/app.js":     lambda: self._serve_static("static/js/app.js", "application/javascript"),
            "/api/databases":  lambda: self._api_databases(),
            "/api/facets":     lambda: self._api_facets(qs),
            "/api/query":      lambda: self._api_query(qs),
            "/api/export":     lambda: self._api_export(qs),
        }

        handler = routes.get(path)
        if handler:
            handler()
        else:
            self._respond(404, "text/plain", b"Not found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/export-selected":
            self._api_export_selected()
        elif path == "/api/sql":
            self._api_sql()
        else:
            self._respond(404, "text/plain", b"Not found")

    # ---- Helpers ----

    def _get_db(self, qs):
        db_name = qs.get("db", [None])[0]
        if db_name and db_name in self.databases:
            return self.databases[db_name]
        return next(iter(self.databases.values()))

    def _respond(self, code: int, content_type: str, body: bytes):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data):
        body = json.dumps(data, default=str).encode("utf-8")
        self._respond(200, "application/json; charset=utf-8", body)

    def _parse_filters(self, qs: dict) -> dict:
        """Parse filter.col=val query params into {col: [val, ...]}."""
        filters = {}
        for key, values in qs.items():
            if key.startswith("filter."):
                filters[key[7:]] = values
        return filters

    def _serve_static(self, rel_path: str, content_type: str):
        """Serve a file from the package directory."""
        filepath = _PACKAGE_DIR / rel_path
        if not filepath.is_file():
            self._respond(404, "text/plain", b"File not found")
            return
        body = filepath.read_bytes()
        charset = "; charset=utf-8" if content_type.startswith("text") or "javascript" in content_type else ""
        self._respond(200, f"{content_type}{charset}", body)

    def _send_csv(self, rows, columns, filename):
        """Write rows as CSV response."""
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
        body = output.getvalue().encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", f"attachment; filename={filename}")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    # ---- API Endpoints ----

    def _api_databases(self):
        result = {}
        for name, db in self.databases.items():
            result[name] = db.get_table_info()
        self._json(result)

    def _api_facets(self, qs):
        db = self._get_db(qs)
        table = qs.get("table", [db.tables[0] if db.tables else ""])[0]
        if table not in db.tables:
            return self._json({"error": "unknown table"})
        self._json(db.get_facet_values(table))

    def _api_query(self, qs):
        db = self._get_db(qs)
        table = qs.get("table", [db.tables[0]])[0]
        if table not in db.tables:
            return self._json({"error": "unknown table"})

        rows, total, columns = db.query(
            table,
            filters=self._parse_filters(qs),
            search=qs.get("search", [None])[0],
            sort_col=qs.get("sort", [None])[0],
            sort_dir=qs.get("dir", ["asc"])[0],
            page=int(qs.get("page", [1])[0]),
        )
        self._json({
            "rows": rows,
            "total": total,
            "columns": columns,
            "page": int(qs.get("page", [1])[0]),
            "page_size": DEFAULT_PAGE_SIZE,
            "pages": max(1, (total + DEFAULT_PAGE_SIZE - 1) // DEFAULT_PAGE_SIZE),
        })

    def _api_export(self, qs):
        """Export all filtered rows as CSV (GET)."""
        db = self._get_db(qs)
        table = qs.get("table", [db.tables[0]])[0]
        if table not in db.tables:
            return self._respond(400, "text/plain", b"Unknown table")

        rows, columns = db.query_all(
            table,
            filters=self._parse_filters(qs),
            search=qs.get("search", [None])[0],
            sort_col=qs.get("sort", [None])[0],
            sort_dir=qs.get("dir", ["asc"])[0],
        )
        self._send_csv(rows, columns, f"{table}_export.csv")

    def _api_export_selected(self):
        """Export specific rows by ID as CSV (POST with JSON body)."""
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            payload = json.loads(body)
        except (ValueError, json.JSONDecodeError):
            return self._respond(400, "text/plain", b"Invalid JSON body")

        db_name = payload.get("db")
        table = payload.get("table")
        row_ids = payload.get("ids", [])

        db = self.databases.get(db_name) if db_name else next(iter(self.databases.values()))
        if not db or table not in db.tables:
            return self._respond(400, "text/plain", b"Unknown database or table")

        rows, columns = db.query_by_ids(table, row_ids)
        self._send_csv(rows, columns, f"{table}_selected.csv")

    def _api_sql(self):
        """Execute a raw SQL query (POST with JSON body)."""
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            payload = json.loads(body)
        except (ValueError, json.JSONDecodeError):
            return self._json({"error": "Invalid JSON body"})

        sql = payload.get("sql", "").strip()
        db_name = payload.get("db")

        if not sql:
            return self._json({"error": "Empty SQL query"})

        db = self.databases.get(db_name) if db_name else next(iter(self.databases.values()))
        if not db:
            return self._json({"error": "Unknown database"})

        try:
            result = db.execute_raw_sql(sql)
            self._json(result)
        except ValueError as e:
            self._json({"error": str(e)})
        except Exception as e:
            self._json({"error": str(e)})
