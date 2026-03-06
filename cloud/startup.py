"""
Download .db from GCS before the server starts.

Requires: google-cloud-storage
Env vars:
    GCS_BUCKET   - bucket name (e.g. carta-genum-st-data)
    DB_FILENAME  - object name (default: spatial_transcriptomics.db)

If GCS_BUCKET is not set, this script is a no-op (local dev fallback).
"""

import os
import sys


def download_db():
    bucket_name = os.environ.get("GCS_BUCKET")
    if not bucket_name:
        print("GCS_BUCKET not set — skipping GCS download (local dev mode)")
        return

    db_filename = os.environ.get("DB_FILENAME", "spatial_transcriptomics.db")
    dest_path = os.path.join("/app", db_filename)

    try:
        from google.cloud import storage
    except ImportError:
        print("google-cloud-storage not installed — skipping GCS download",
              file=sys.stderr)
        return

    print(f"Downloading gs://{bucket_name}/{db_filename} -> {dest_path}")
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(db_filename)

    if not blob.exists():
        print(f"Warning: gs://{bucket_name}/{db_filename} does not exist yet",
              file=sys.stderr)
        return

    blob.download_to_filename(dest_path)
    size_mb = os.path.getsize(dest_path) / (1024 * 1024)
    print(f"Downloaded {db_filename} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    download_db()
