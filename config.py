"""Single source of truth for env-var driven config. Nothing here is hardcoded
so the same code runs locally (sqlite fallback, dry-run sends) and on Render
(real Supabase Postgres, real Stripe/SendGrid) purely based on which env vars
are set.
"""
import os

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-key-change-me")

# Falls back to a local sqlite file when DATABASE_URL isn't set (no Supabase
# creds available yet) so the app is runnable for local template/route work.
# Render must set DATABASE_URL to the Supabase Postgres connection string.
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///local_dev.db")

SUPABASE_URL = os.environ.get("SUPABASE_URL")  # e.g. https://tsxhuzsanoqahsrbumxz.supabase.co
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
VIDEO_BUCKET = os.environ.get("SUPABASE_VIDEO_BUCKET", "lesson-videos")
PDF_BUCKET = os.environ.get("SUPABASE_PDF_BUCKET", "lesson-pdfs")
SIGNED_URL_TTL_SECONDS = int(os.environ.get("SIGNED_URL_TTL_SECONDS", "3600"))

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")

SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "noreply@aimadesimple40.com")
FROM_NAME = os.environ.get("FROM_NAME", "AI Made Simple 40+")

PORTAL_BASE_URL = os.environ.get("PORTAL_BASE_URL", "http://localhost:5000")

if __name__ == "__main__":
    # Synthetic self-test: defaults must be safe to boot with zero env vars set.
    assert DATABASE_URL.startswith("sqlite:///") or DATABASE_URL.startswith("postgres")
    assert SIGNED_URL_TTL_SECONDS > 0
    assert FROM_EMAIL and "@" in FROM_EMAIL
    print("config.py self-test passed")
