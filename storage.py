"""Signed URLs for the private `lesson-pdfs` Supabase Storage bucket, via
raw REST calls -- same `requests`-only pattern already used in
marketing-platform/db.py rather than pulling in the supabase-py SDK for one
endpoint.

Videos are NOT here -- they're unlisted YouTube embeds (see
lessons_config.py's youtube_embed_url) because Supabase's project-level
50MB file-size cap can't hold 200-320MB course videos.

The `lesson-pdfs` bucket must exist as PRIVATE in the Supabase dashboard,
with the 8 PDFs uploaded using the exact filenames in lessons_config.py
(e.g. "Module 1 Printable Script.pdf") -- already done via upload_lessons.py.
"""
import requests

import config


class StorageError(RuntimeError):
    pass


def get_signed_url(bucket, object_path, expires_in=None):
    """Returns a time-limited download URL for a private-bucket object."""
    if not config.SUPABASE_URL or not config.SUPABASE_SERVICE_KEY:
        raise StorageError(
            "SUPABASE_URL / SUPABASE_SERVICE_KEY not configured -- set them "
            "as env vars (Render dashboard in production) before lesson "
            "pages can serve real PDF links."
        )

    expires_in = expires_in or config.SIGNED_URL_TTL_SECONDS
    endpoint = f"{config.SUPABASE_URL}/storage/v1/object/sign/{bucket}/{object_path}"
    headers = {
        "Authorization": f"Bearer {config.SUPABASE_SERVICE_KEY}",
        "apikey": config.SUPABASE_SERVICE_KEY,
        "Content-Type": "application/json",
    }
    resp = requests.post(endpoint, json={"expiresIn": expires_in}, headers=headers, timeout=10)
    if resp.status_code != 200:
        raise StorageError(f"Supabase Storage sign failed ({resp.status_code}): {resp.text}")

    signed_path = resp.json().get("signedURL")
    if not signed_path:
        raise StorageError(f"Supabase Storage response missing signedURL: {resp.text}")

    return f"{config.SUPABASE_URL}/storage/v1{signed_path}"


def get_pdf_url(lesson):
    """Returns a signed download URL for a lesson dict from lessons_config.py."""
    return get_signed_url(config.PDF_BUCKET, lesson["pdf_path"])


if __name__ == "__main__":
    # No real Supabase creds available in this environment -- self-test only
    # covers the fail-fast path, not an actual signed round-trip.
    config.SUPABASE_URL = None
    config.SUPABASE_SERVICE_KEY = None
    try:
        get_signed_url("lesson-pdfs", "Module 1 Printable Script.pdf")
        raise AssertionError("expected StorageError when unconfigured")
    except StorageError:
        pass
    print("storage.py self-test passed")
