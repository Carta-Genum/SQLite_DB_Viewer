"""
Download .db files from GCS before the server starts.

Requires: google-cloud-storage
Env vars:
    GCS_DATABASES  - comma-separated list of "bucket:filename" pairs
                     e.g. "samples_scraper:spatial_transcriptomics.db,contacts_scraper:contacts.db"
    GCS_BUCKET     - (legacy) single bucket name, used with DB_FILENAME
    DB_FILENAME    - (legacy) single object name (default: spatial_transcriptomics.db)

If neither GCS_DATABASES nor GCS_BUCKET is set, this script is a no-op (local dev fallback).
"""

import os
import sys


def _parse_databases() -> list[tuple[str, str]]:
    """Return list of (bucket_name, filename) pairs to download."""
    gcs_databases = os.environ.get("GCS_DATABASES")
    if gcs_databases:
        pairs = []
        for entry in gcs_databases.split(","):
            entry = entry.strip()
            if ":" not in entry:
                print(f"Error: invalid GCS_DATABASES entry '{entry}' — expected 'bucket:filename'",
                      file=sys.stderr)
                sys.exit(1)
            bucket, filename = entry.split(":", 1)
            pairs.append((bucket.strip(), filename.strip()))
        return pairs

    # Legacy single-db fallback
    bucket_name = os.environ.get("GCS_BUCKET")
    if bucket_name:
        db_filename = os.environ.get("DB_FILENAME", "spatial_transcriptomics.db")
        return [(bucket_name, db_filename)]

    return []


def download_db():
    databases = _parse_databases()
    if not databases:
        print("GCS_DATABASES and GCS_BUCKET not set — skipping GCS download (local dev mode)")
        return

    try:
        from google.cloud import storage
    except ImportError:
        print("google-cloud-storage not installed — skipping GCS download",
              file=sys.stderr)
        return

    client = storage.Client()

    for bucket_name, db_filename in databases:
        dest_path = os.path.join("/app", db_filename)
        print(f"Downloading gs://{bucket_name}/{db_filename} -> {dest_path}")
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(db_filename)

        if not blob.exists():
            print(f"Error: gs://{bucket_name}/{db_filename} does not exist in bucket",
                  file=sys.stderr)
            sys.exit(1)

        blob.download_to_filename(dest_path)
        size_mb = os.path.getsize(dest_path) / (1024 * 1024)
        print(f"Downloaded {db_filename} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    download_db()
