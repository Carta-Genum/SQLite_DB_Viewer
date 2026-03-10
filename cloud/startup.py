"""
Download .db files from GCS before the server starts.

Requires: google-cloud-storage

Env vars:
    GCS_DATABASES - comma-separated list of bucket:filename pairs
                    e.g. "samples_scraper:spatial_transcriptomics.db,other_bucket:other.db"
    GCS_BUCKET    - (legacy) single bucket name, used with DB_FILENAME
    DB_FILENAME   - (legacy) single object name (default: spatial_transcriptomics.db)

If neither GCS_DATABASES nor GCS_BUCKET is set, this script is a no-op (local dev fallback).
"""

import os
import sys


def download_db(bucket_name: str, db_filename: str):
    """Download a single .db file from GCS to /app/."""
    from google.cloud import storage

    dest_path = os.path.join("/app", db_filename)

    print(f"Downloading gs://{bucket_name}/{db_filename} -> {dest_path}")
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(db_filename)

    if not blob.exists():
        print(f"Error: gs://{bucket_name}/{db_filename} does not exist in bucket",
              file=sys.stderr)
        sys.exit(1)

    blob.download_to_filename(dest_path)
    size_mb = os.path.getsize(dest_path) / (1024 * 1024)
    print(f"Downloaded {db_filename} ({size_mb:.1f} MB)")


def main():
    # New multi-database format: "bucket1:file1.db,bucket2:file2.db"
    gcs_databases = os.environ.get("GCS_DATABASES")

    if gcs_databases:
        try:
            from google.cloud import storage  # noqa: F401
        except ImportError:
            print("google-cloud-storage not installed — skipping GCS download",
                  file=sys.stderr)
            return

        for entry in gcs_databases.split(","):
            entry = entry.strip()
            if not entry:
                continue
            if ":" not in entry:
                print(f"Error: invalid GCS_DATABASES entry '{entry}' — expected bucket:filename",
                      file=sys.stderr)
                sys.exit(1)
            bucket_name, db_filename = entry.split(":", 1)
            download_db(bucket_name, db_filename)
        return

    # Legacy single-database format
    bucket_name = os.environ.get("GCS_BUCKET")
    if not bucket_name:
        print("GCS_DATABASES and GCS_BUCKET not set — skipping GCS download (local dev mode)")
        return

    try:
        from google.cloud import storage  # noqa: F401
    except ImportError:
        print("google-cloud-storage not installed — skipping GCS download",
              file=sys.stderr)
        return

    db_filename = os.environ.get("DB_FILENAME", "spatial_transcriptomics.db")
    download_db(bucket_name, db_filename)


if __name__ == "__main__":
    main()