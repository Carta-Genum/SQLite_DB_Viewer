"""Tests for the database module."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from stdb_viewer.database import Database


@pytest.fixture
def sample_db(tmp_path):
    """Create a small test database."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE experiments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            organism TEXT,
            technology TEXT,
            tissue TEXT,
            score REAL
        )
    """)
    rows = [
        ("Exp A", "Mouse", "Visium", "brain", 0.95),
        ("Exp B", "Mouse", "Visium", "lung", 0.88),
        ("Exp C", "Human", "MERFISH", "brain", 0.72),
        ("Exp D", "Human", "Visium", "liver", 0.91),
        ("Exp E", "Mouse", "MERFISH", "brain", 0.65),
        ("Exp F", "Human", "CosMx", "lung", 0.80),
    ]
    conn.executemany(
        "INSERT INTO experiments (name, organism, technology, tissue, score) VALUES (?,?,?,?,?)",
        rows,
    )
    conn.execute("CREATE TABLE _schema_version (v INTEGER)")  # should be skipped
    conn.commit()
    conn.close()
    return str(db_path)


class TestDatabaseDiscovery:
    def test_discovers_tables(self, sample_db):
        db = Database(sample_db)
        assert "experiments" in db.tables
        assert "_schema_version" not in db.tables

    def test_get_columns(self, sample_db):
        db = Database(sample_db)
        cols = db.get_column_names("experiments")
        assert cols == ["id", "name", "organism", "technology", "tissue", "score"]

    def test_table_info(self, sample_db):
        db = Database(sample_db)
        info = db.get_table_info()
        assert info["experiments"]["count"] == 6

    def test_facets_detected(self, sample_db):
        db = Database(sample_db)
        facets = db.get_facets("experiments")
        # organism, technology, tissue should be facets (2-3 distinct values)
        assert "organism" in facets
        assert "technology" in facets
        assert "tissue" in facets
        # id and name should NOT be facets (never_facet or unique)
        assert "id" not in facets
        assert "name" not in facets


class TestFacetValues:
    def test_facet_values(self, sample_db):
        db = Database(sample_db)
        facets = db.get_facet_values("experiments")
        organisms = {v["value"] for v in facets["organism"]["values"]}
        assert organisms == {"Mouse", "Human"}

    def test_facet_counts(self, sample_db):
        db = Database(sample_db)
        facets = db.get_facet_values("experiments")
        tech_counts = {
            v["value"]: v["count"] for v in facets["technology"]["values"]
        }
        assert tech_counts["Visium"] == 3
        assert tech_counts["MERFISH"] == 2
        assert tech_counts["CosMx"] == 1


@pytest.fixture
def ontology_db(tmp_path):
    """Database mirroring the production schema: human-readable annotation
    columns alongside their machine-readable ontology CURIE twins, plus a
    pathology vocabulary just above the old cardinality cap (80)."""
    db_path = tmp_path / "onto.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE datasets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            organism TEXT,
            organism_ncbi_taxon_id TEXT,
            tissue_type TEXT,
            tissue_uberon_id TEXT,
            pathology TEXT,
            pathology_mondo_id TEXT
        )
    """)
    rows = []
    # 90 distinct pathology terms (above MAX_FACET_CARDINALITY pre-fix = 80),
    # each appearing in >=2 rows so it survives the bucket-average filter.
    for i in range(90):
        for _ in range(3):
            rows.append((
                "GEO", "Human", "NCBITaxon:9606",
                "lung", "UBERON:0002048",
                f"disease_{i:03d}", f"MONDO:{i:07d}",
            ))
    conn.executemany(
        "INSERT INTO datasets (source, organism, organism_ncbi_taxon_id, "
        "tissue_type, tissue_uberon_id, pathology, pathology_mondo_id) "
        "VALUES (?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    conn.close()
    return str(db_path)


class TestOntologyFacets:
    def test_ontology_id_columns_excluded(self, ontology_db):
        facets = Database(ontology_db).get_facets("datasets")
        assert "tissue_uberon_id" not in facets
        assert "pathology_mondo_id" not in facets
        assert "organism_ncbi_taxon_id" not in facets

    def test_human_readable_columns_kept(self, ontology_db):
        facets = Database(ontology_db).get_facets("datasets")
        # source is single-value TEXT — kept; organism/tissue_type are facets
        assert "source" in facets
        assert "organism" in facets
        assert "tissue_type" in facets

    def test_pathology_vocabulary_above_old_cap_is_offered(self, ontology_db):
        # 90 distinct terms would have been dropped by the old cap of 80.
        facets = Database(ontology_db).get_facets("datasets")
        assert "pathology" in facets


@pytest.fixture
def samples_db(tmp_path):
    """samples table with a high-cardinality tissue vocabulary (> cap)."""
    db_path = tmp_path / "samples.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organism TEXT, tissue TEXT, region TEXT, disease TEXT
        )
    """)
    rows = []
    for i in range(150):  # 150 distinct tissues — well above the cap
        for _ in range(2):
            rows.append(("Human", f"tissue_{i:03d}", f"region_{i:03d}",
                         f"disease_{i:03d}"))
    conn.executemany(
        "INSERT INTO samples (organism, tissue, region, disease) VALUES (?,?,?,?)",
        rows,
    )
    conn.commit()
    conn.close()
    return str(db_path)


class TestForceFacets:
    def test_high_cardinality_samples_columns_offered(self, samples_db):
        facets = Database(samples_db).get_facets("samples")
        assert "tissue" in facets
        assert "region" in facets
        assert "disease" in facets
        assert "organism" in facets


class TestQuery:
    def test_basic_query(self, sample_db):
        db = Database(sample_db)
        rows, total, cols = db.query("experiments")
        assert total == 6
        assert len(rows) == 6

    def test_filter(self, sample_db):
        db = Database(sample_db)
        rows, total, _ = db.query("experiments", filters={"organism": ["Mouse"]})
        assert total == 3
        assert all(r["organism"] == "Mouse" for r in rows)

    def test_multi_filter(self, sample_db):
        db = Database(sample_db)
        rows, total, _ = db.query(
            "experiments",
            filters={"organism": ["Mouse"], "technology": ["Visium"]},
        )
        assert total == 2

    def test_search(self, sample_db):
        db = Database(sample_db)
        rows, total, _ = db.query("experiments", search="brain")
        assert total == 3

    def test_sort_asc(self, sample_db):
        db = Database(sample_db)
        rows, _, _ = db.query("experiments", sort_col="score", sort_dir="asc")
        scores = [r["score"] for r in rows]
        assert scores == sorted(scores)

    def test_sort_desc(self, sample_db):
        db = Database(sample_db)
        rows, _, _ = db.query("experiments", sort_col="score", sort_dir="desc")
        scores = [r["score"] for r in rows]
        assert scores == sorted(scores, reverse=True)

    def test_pagination(self, sample_db):
        db = Database(sample_db)
        rows, total, _ = db.query("experiments", page=1, page_size=2)
        assert total == 6
        assert len(rows) == 2

        rows2, _, _ = db.query("experiments", page=2, page_size=2)
        assert len(rows2) == 2
        assert rows[0]["id"] != rows2[0]["id"]

    def test_query_all_for_export(self, sample_db):
        db = Database(sample_db)
        rows, cols = db.query_all(
            "experiments", filters={"tissue": ["brain"]}
        )
        assert len(rows) == 3
        assert "name" in cols
