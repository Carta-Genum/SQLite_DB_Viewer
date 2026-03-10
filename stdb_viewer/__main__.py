"""
CLI entry point.

Usage:
    python -m stdb_viewer                         # serve all .db in cwd
    python -m stdb_viewer -d mydata.db -p 9000    # specific db + port
    python -m stdb_viewer -d a.db -d b.db         # multiple databases
"""

import argparse
import os
import sys
import threading
import webbrowser
from http.server import HTTPServer
from pathlib import Path

from .database import Database
from .handler import ViewerHandler


def parse_args():
    # Cloud Run sets PORT env var; use it as default if present
    default_port = int(os.environ.get("PORT", 8025))

    parser = argparse.ArgumentParser(
        prog="stdb-viewer",
        description="Serve SQLite databases as a browsable web application.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python -m stdb_viewer                          # all .db files in current dir
  python -m stdb_viewer -d mydata.db             # specific database
  python -m stdb_viewer -d db1.db -d db2.db      # multiple databases
  python -m stdb_viewer -p 9000                  # custom port
        """,
    )
    parser.add_argument(
        "-d", "--database", action="append", default=None,
        help="Path to a .db file (repeatable for multiple databases)",
    )
    parser.add_argument(
        "-p", "--port", type=int, default=default_port,
        help="Port to serve on (default: %(default)s)",
    )
    parser.add_argument(
        "--host", default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--no-browser", action="store_true",
        help="Don't open the browser automatically",
    )
    return parser.parse_args()


def load_databases(paths: list[str]) -> dict[str, Database]:
    """Load and validate database files, return {name: Database}."""
    databases = {}
    for path in paths:
        if not os.path.exists(path):
            print(f"  ✗ {path} — file not found", file=sys.stderr)
            sys.exit(1)
        db = Database(path)
        databases[db.name] = db
        table_info = db.get_table_info()
        total_rows = sum(v["count"] for v in table_info.values())
        print(f"  📂 {db.name}: {len(db.tables)} tables, {total_rows:,} rows")
        for t, info in table_info.items():
            facets = db.facets.get(t, [])
            print(f"     └─ {t}: {info['count']:,} rows, "
                  f"{len(facets)} filters ({', '.join(facets)})")
    return databases


def main():
    args = parse_args()

    # Discover databases
    db_paths = args.database
    if not db_paths:
        db_paths = sorted(str(p) for p in Path(".").glob("*.db"))
    if not db_paths:
        print("Error: No .db files found. Use -d to specify a database path.",
              file=sys.stderr)
        sys.exit(1)

    print()
    databases = load_databases(db_paths)
    ViewerHandler.databases = databases

    server = HTTPServer((args.host, args.port), ViewerHandler)
    url = f"http://localhost:{args.port}"
    print(f"\n  🚀 Viewer running at {url}")
    print(f"     Press Ctrl+C to stop\n")

    if not args.no_browser:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
