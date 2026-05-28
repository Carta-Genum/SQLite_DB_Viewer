"""
Database abstraction layer.

Wraps SQLite databases with introspection, faceted filtering,
full-text search, sorting, and pagination — all server-side.
"""

import sqlite3
import threading
from pathlib import Path

# ---- Configuration ----

# Tables to hide from the UI
SKIP_TABLES = frozenset({
    "_schema_version", "sqlite_sequence", "sqlite_stat1",
    "sqlite_stat2", "sqlite_stat3", "sqlite_stat4",
})

# Max distinct values for a column to be offered as a facet filter.
# Set above the typical pathology/tissue vocabulary size so human-readable
# annotation columns (e.g. datasets.pathology, ~89 terms) are offered as
# filters rather than silently dropped.
MAX_FACET_CARDINALITY = 100

# Minimum average rows-per-value for a column to be useful as a facet.
# Below this, picking any value only matches ~1 row — that's a search, not a
# filter — so the column is excluded (e.g. run_id, timestamps, per-run counters).
MIN_FACET_BUCKET_AVG = 2

# Columns that should never become facets (unique / free-text / internal)
NEVER_FACET = frozenset({
    "id", "description", "characteristics", "data_files",
    "url", "download_url", "created_at", "updated_at",
    "md5", "sra_accession", "authors", "related_doi",
    "dataset_name", "sample_name", "filename",
    "dataset_id", "sample_id", "geo_accession",
    "publish_date", "section_count", "gsm_count", "size_bytes",
    # files archival columns
    "gcs_path", "archive_error", "archived_at",
    # long free-text / JSON / log columns from runs & validation_log
    "classification_json", "prompt", "response",
    "cli_args_json", "environment_json", "corrections",
    "dictionary_matched", "error_message", "log_path",
})

# Ontology cross-reference columns hold machine-readable CURIE IDs
# (e.g. UBERON:0002048, MONDO:0005061, NCBITaxon:9606) that mirror a
# human-readable column (tissue, pathology, organism). They are low
# cardinality and would otherwise pass facet detection, surfacing as
# filters in place of the human-friendly terms — so exclude them by suffix.
ONTOLOGY_ID_SUFFIXES = (
    "_uberon_id", "_mondo_id", "_ncbi_taxon_id", "_efo_id", "_cl_id",
)

# Columns offered as facets even though their distinct count exceeds
# MAX_FACET_CARDINALITY. These are high-value biological vocabularies the UI
# makes usable via a type-to-filter search box inside the facet group.
FORCE_FACET = {
    "samples": frozenset({"tissue", "region", "disease"}),
}

# Tables that are operational/admin (hidden behind an explicit toggle in the UI).
# Server still serves them; the client controls visibility.
ADMIN_TABLES = frozenset({"runs", "validation_log"})

# Default page size
DEFAULT_PAGE_SIZE = 200


class Database:
    """Read-only wrapper around a single SQLite database file."""

    def __init__(self, path: str):
        self.path = path
        self.name = Path(path).stem
        self._local = threading.local()
        self.tables = self._discover_tables()
        self._col_types = {t: dict(self.get_columns(t)) for t in self.tables}
        # Facets are discovered lazily per table on first access (see
        # get_facets). Discovering them all at startup is slow for large
        # tables (a COUNT(DISTINCT) per column over 100k+ rows), so we defer
        # it until a table is actually opened.
        self.facets: dict[str, list[str]] = {}

    @property
    def conn(self) -> sqlite3.Connection:
        """Thread-local read-only connection.

        ThreadingHTTPServer serves each request in its own thread, and a single
        sqlite3 connection cannot be shared across threads. Each thread lazily
        gets its own read-only connection; concurrent reads are safe in SQLite.
        """
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(
                f"file:{self.path}?mode=ro", uri=True, check_same_thread=False
            )
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    # ---- Introspection ----

    def _discover_tables(self) -> list[str]:
        cur = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        return [r["name"] for r in cur if r["name"] not in SKIP_TABLES]

    def get_columns(self, table: str) -> list[tuple[str, str]]:
        """Return [(col_name, col_type), ...] for a table."""
        cur = self.conn.execute(f"PRAGMA table_info([{table}])")
        return [(r["name"], r["type"]) for r in cur]

    def get_column_names(self, table: str) -> list[str]:
        return [c[0] for c in self.get_columns(table)]

    def _is_numeric_column(self, table: str, col: str) -> bool:
        """Check if a column holds numeric data (by type or by naming pattern)."""
        col_type = self._col_types.get(table, {}).get(col, "").upper()
        if any(t in col_type for t in ("INT", "REAL", "FLOAT", "NUM", "DOUBLE")):
            return True
        # TEXT affinity (TEXT/CHAR/CLOB) wins over the _id/_pk suffix heuristic —
        # otherwise text accessions like "GSE12345" get sorted as REAL → 0.
        if any(t in col_type for t in ("TEXT", "CHAR", "CLOB")):
            return False
        # Fallback for empty/unknown declared types: use naming convention.
        if col.endswith("_pk") or col.endswith("_id") or col == "id":
            return True
        return False

    def _discover_facets(self, table: str) -> list[str]:
        """Identify columns suitable for checkbox filtering."""
        facets = []
        force = FORCE_FACET.get(table, frozenset())
        total = self.conn.execute(
            f"SELECT COUNT(*) FROM [{table}]"
        ).fetchone()[0]
        for name, _ in self.get_columns(table):
            if name in NEVER_FACET:
                continue
            # Skip ontology CURIE columns (tissue_uberon_id, pathology_mondo_id,
            # organism_ncbi_taxon_id, ...) in favour of their human-readable twin.
            if name.endswith(ONTOLOGY_ID_SUFFIXES):
                continue
            # Force-included high-cardinality vocabularies bypass the cap; the
            # UI makes them usable with a per-facet search box.
            if name in force:
                facets.append(name)
                continue
            try:
                cur = self.conn.execute(
                    f"SELECT COUNT(DISTINCT [{name}]) AS c "
                    f"FROM [{table}] WHERE [{name}] IS NOT NULL"
                )
                n = cur.fetchone()["c"]
                if n == 0 or n > MAX_FACET_CARDINALITY:
                    continue
                # A single-value column is informative for TEXT (e.g.
                # source='GEO' across all rows) but noise for numerics
                # (e.g. samples_seen=0 across all runs).
                col_type = self._col_types.get(table, {}).get(name, "").upper()
                is_text = any(t in col_type for t in ("TEXT", "CHAR", "CLOB"))
                if n == 1 and not is_text:
                    continue
                # Drop near-unique multi-value columns: each value must
                # bucket MIN_FACET_BUCKET_AVG rows on average.
                if n > 1 and total > 0 and n * MIN_FACET_BUCKET_AVG > total:
                    continue
                facets.append(name)
            except sqlite3.OperationalError:
                pass
        return facets

    def get_table_info(self) -> dict:
        """Return summary {table: {count, columns, admin}} for all visible tables."""
        info = {}
        for t in self.tables:
            cnt = self.conn.execute(
                f"SELECT COUNT(*) AS c FROM [{t}]"
            ).fetchone()["c"]
            info[t] = {
                "count": cnt,
                "columns": self.get_column_names(t),
                "admin": t in ADMIN_TABLES,
            }
        return info

    # ---- Facets ----

    def get_facets(self, table: str) -> list[str]:
        """Facet columns for a table, discovered lazily and cached.

        Admin tables are not discovered at startup; the first request for
        their facets computes and caches the result here.
        """
        cols = self.facets.get(table)
        if cols is None:
            cols = self._discover_facets(table)
            self.facets[table] = cols
        return cols

    def get_facet_values(self, table: str) -> dict:
        """
        Return {col: {values: [{value, count}, ...], numeric: bool}}.

        Numeric columns are sorted by value ASC (natural order).
        Text columns are sorted by count DESC then value ASC.
        """
        result = {}
        for col in self.get_facets(table):
            is_num = self._is_numeric_column(table, col)
            if is_num:
                order = f"CAST([{col}] AS REAL) ASC"
            else:
                order = "c DESC, v ASC"
            cur = self.conn.execute(
                f"SELECT [{col}] AS v, COUNT(*) AS c "
                f"FROM [{table}] WHERE [{col}] IS NOT NULL "
                f"GROUP BY [{col}] ORDER BY {order}"
            )
            result[col] = {
                "values": [{"value": r["v"], "count": r["c"]} for r in cur],
                "numeric": is_num,
            }
        return result

    # ---- Query ----

    def _build_where(
        self, table: str, filters: dict | None, search: str | None
    ) -> tuple[str, list]:
        """Build WHERE clause + params from filters and search term."""
        col_names = self.get_column_names(table)
        wheres, params = [], []

        if filters:
            for col, values in filters.items():
                if col not in col_names:
                    continue
                placeholders = ",".join("?" for _ in values)
                wheres.append(f"[{col}] IN ({placeholders})")
                params.extend(values)

        if search:
            clauses = []
            for c in col_names:
                clauses.append(f"CAST([{c}] AS TEXT) LIKE ?")
                params.append(f"%{search}%")
            wheres.append(f"({' OR '.join(clauses)})")

        where_sql = (" WHERE " + " AND ".join(wheres)) if wheres else ""
        return where_sql, params

    def query(
        self,
        table: str,
        filters: dict | None = None,
        search: str | None = None,
        sort_col: str | None = None,
        sort_dir: str = "asc",
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[dict], int, list[str]]:
        """
        Query with optional filters, search, sort, and pagination.

        Returns:
            (rows, total_count, column_names)
        """
        col_names = self.get_column_names(table)
        where_sql, params = self._build_where(table, filters, search)

        # Total count
        total = self.conn.execute(
            f"SELECT COUNT(*) AS c FROM [{table}]{where_sql}", params
        ).fetchone()["c"]

        # Sort
        order_sql = ""
        if sort_col and sort_col in col_names:
            direction = "ASC" if sort_dir == "asc" else "DESC"
            order_sql = f" ORDER BY [{sort_col}] {direction} NULLS LAST"

        # Paginate
        offset = (page - 1) * page_size
        limit_sql = f" LIMIT {page_size} OFFSET {offset}"

        cur = self.conn.execute(
            f"SELECT * FROM [{table}]{where_sql}{order_sql}{limit_sql}",
            params,
        )
        rows = [dict(r) for r in cur]
        return rows, total, col_names

    def query_all(
        self,
        table: str,
        filters: dict | None = None,
        search: str | None = None,
        sort_col: str | None = None,
        sort_dir: str = "asc",
    ) -> tuple[list[dict], list[str]]:
        """Query without pagination — for CSV export."""
        col_names = self.get_column_names(table)
        where_sql, params = self._build_where(table, filters, search)

        order_sql = ""
        if sort_col and sort_col in col_names:
            direction = "ASC" if sort_dir == "asc" else "DESC"
            order_sql = f" ORDER BY [{sort_col}] {direction} NULLS LAST"

        cur = self.conn.execute(
            f"SELECT * FROM [{table}]{where_sql}{order_sql}", params
        )
        return [dict(r) for r in cur], col_names

    def execute_raw_sql(self, sql: str, max_rows: int = 2000) -> dict:
        """
        Execute a raw read-only SQL statement.

        Returns:
            {columns: [...], rows: [{...}, ...], row_count: int, truncated: bool}
        Raises ValueError for write statements.
        """
        stripped = sql.strip().rstrip(";").strip()
        first_word = stripped.split()[0].upper() if stripped else ""
        if first_word not in (
            "SELECT", "PRAGMA", "EXPLAIN", "WITH",
        ):
            raise ValueError(
                f"Only SELECT / PRAGMA / EXPLAIN / WITH statements are allowed "
                f"(got '{first_word}')"
            )

        cur = self.conn.execute(sql)
        if cur.description is None:
            return {"columns": [], "rows": [], "row_count": 0, "truncated": False}

        columns = [d[0] for d in cur.description]
        rows = []
        truncated = False
        for i, row in enumerate(cur):
            if i >= max_rows:
                truncated = True
                break
            rows.append(dict(zip(columns, row)))
        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "truncated": truncated,
        }

    def query_by_ids(
        self,
        table: str,
        row_ids: list,
    ) -> tuple[list[dict], list[str]]:
        """Fetch specific rows by their `id` column — for selective CSV export."""
        col_names = self.get_column_names(table)
        if "id" not in col_names or not row_ids:
            return [], col_names

        placeholders = ",".join("?" for _ in row_ids)
        cur = self.conn.execute(
            f"SELECT * FROM [{table}] WHERE [id] IN ({placeholders})",
            row_ids,
        )
        return [dict(r) for r in cur], col_names
