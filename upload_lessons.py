"""One-off setup script: creates the private `lesson-pdfs` Supabase Storage
bucket and uploads the 8 printable-script PDFs from Rick's Desktop.

Course videos are NOT handled here -- they're unlisted YouTube uploads
(see lessons_config.py) because Supabase's project-level 50MB file-size cap
can't hold 200-320MB course videos.

Requires SUPABASE_URL + SUPABASE_SERVICE_KEY in .env (gitignored, never
committed). Safe to re-run -- bucket creation and uploads are both
idempotent (x-upsert overwrites existing objects).
"""
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SERVICE_KEY:
    sys.exit("SUPABASE_URL / SUPABASE_SERVICE_KEY not set in .env")

PDF_DIR = Path(r"C:\Users\User\Desktop\Modules 1-8 Printable Scripts")
PDF_BUCKET = "lesson-pdfs"

AUTH_HEADERS = {
    "Authorization": f"Bearer {SERVICE_KEY}",
    "apikey": SERVICE_KEY,
}


def local_pdf_path(i):
    return PDF_DIR / f"Module {i} Printable Script.pdf"


def ensure_bucket(bucket_id, mime_types, size_limit):
    resp = requests.post(
        f"{SUPABASE_URL}/storage/v1/bucket",
        json={
            "id": bucket_id,
            "name": bucket_id,
            "public": False,
            "file_size_limit": size_limit,
            "allowed_mime_types": mime_types,
        },
        headers={**AUTH_HEADERS, "Content-Type": "application/json"},
        timeout=30,
    )
    if resp.status_code in (200, 201):
        print(f"created bucket '{bucket_id}'")
    elif resp.status_code == 400 and (
        "already exists" in resp.text.lower() or "duplicate" in resp.text.lower()
    ):
        print(f"bucket '{bucket_id}' already exists, continuing")
    else:
        raise RuntimeError(f"failed to create bucket '{bucket_id}': {resp.status_code} {resp.text}")


def upload_file(bucket, object_name, local_path, content_type):
    if not local_path.exists():
        return False, f"local file not found: {local_path}"

    url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{requests.utils.quote(object_name)}"
    headers = {
        **AUTH_HEADERS,
        "Content-Type": content_type,
        "x-upsert": "true",
    }
    size_mb = local_path.stat().st_size / 1_000_000
    with open(local_path, "rb") as f:
        resp = requests.post(url, data=f, headers=headers, timeout=900)

    if resp.status_code not in (200, 201):
        return False, f"{resp.status_code}: {resp.text[:300]}"
    return True, f"{size_mb:.0f}MB"


def main():
    ensure_bucket(PDF_BUCKET, ["application/pdf"], "20MB")

    results = []
    for i in range(1, 9):
        object_name = f"Module {i} Printable Script.pdf"
        local_path = local_pdf_path(i)
        print(f"uploading {object_name} ...", flush=True)
        ok, detail = upload_file(PDF_BUCKET, object_name, local_path, "application/pdf")
        results.append((object_name, ok, detail))
        print(f"  {'OK' if ok else 'FAILED'} - {detail}")

    succeeded = sum(1 for _, ok, _ in results if ok)
    print(f"\n{succeeded}/{len(results)} PDFs uploaded successfully")
    if succeeded != len(results):
        print("Failures:")
        for name, ok, detail in results:
            if not ok:
                print(f"  - {name}: {detail}")
        sys.exit(1)


if __name__ == "__main__":
    main()
