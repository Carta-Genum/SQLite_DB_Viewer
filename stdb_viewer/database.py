"""
Database abstraction layer.

Wraps SQLite databases with introspection, faceted filtering,
full-text search, sorting, and pagination — all server-side.
"""

import sqlite3
from pathlib import Path

# ---- Configuration ----

# Tables to hide from the UI
SKIP_TABLES = frozenset({
    "_schema_version", "sqlite_sequence", "sqlite_stat1",
    "sqlite_stat2", "sqlite_stat3", "sqlite_stat4",
})

# Max distinct values for a column to be offered as a facet filter
MAX_FACET_CARDINALITY = 80

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
})

# Default page size
DEFAULT_PAGE_SIZE = 200


class Database:
    """Read-only wrapper around a single SQLite database file."""

    def __init__(self, path: str):
        self.path = path
        self.name = Path(path).stem
        self.conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        self.conn.row_factory = sqlite3.Row
        self.tables = self._discover_tables()
        self._col_types = {t: dict(self.get_columns(t)) for t in self.tables}
        self.facets = {t: self._discover_facets(t) for t in self.tables}

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
        # Covers FK columns like dataset_pk, sample_pk
        if col.endswith("_pk") or col.endswith("_id") or col == "id":
            return True
        return False

    def _discover_facets(self, table: str) -> list[str]:
        """Identify columns suitable for checkbox filtering."""
        facets = []
        for name, _ in self.get_columns(table):
            if name in NEVER_FACET:
                continue
            try:
                cur = self.conn.execute(
                    f"SELECT COUNT(DISTINCT [{name}]) AS c "
                    f"FROM [{table}] WHERE [{name}] IS NOT NULL"
                )
                n = cur.fetchone()["c"]
                if 1 < n <= MAX_FACET_CARDINALITY:
                    facets.append(name)
            except sqlite3.OperationalError:
                pass
        return facets

    def get_table_info(self) -> dict:
        """Return summary {table: {count, columns}} for all visible tables."""
        info = {}
        for t in self.tables:
            cnt = self.conn.execute(
                f"SELECT COUNT(*) AS c FROM [{t}]"
            ).fetchone()["c"]
            info[t] = {
                "count": cnt,
                "columns": self.get_column_names(t),
            }
        return info

    # ---- Facets ----

    def get_facet_values(self, table: str) -> dict:
        """
        Return {col: {values: [{value, count}, ...], numeric: bool}}.

        Numeric columns are sorted by value ASC (natural order).
        Text columns are sorted by count DESC then value ASC.
        """
        result = {}
        for col in self.facets.get(table, []):
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
