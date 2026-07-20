"""One-off verification script: fires a real, correctly-signed
checkout.session.completed event at the LIVE Render webhook endpoint, using
a clearly-tagged test email, so the Stripe->portal->Supabase flow can be
proven without an actual $87 charge.

Requires STRIPE_WEBHOOK_SECRET in .env (gitignored, never committed) --
the same whsec_... value already set in Render's env vars, just copied
locally so this script can sign a payload the same way Stripe does.

Verifies the resulting row via the Supabase REST API (using
SUPABASE_SERVICE_KEY, which bypasses RLS) rather than needing the Postgres
DATABASE_URL/password directly.

Usage:
    python test_webhook.py            # first delivery -- expect a new row
    python test_webhook.py            # run again -- expect idempotent no-op
    python test_webhook.py --cleanup  # delete the test row from Supabase
"""
import hashlib
import hmac
import json
import os
import sys
import time
import uuid

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

WEBHOOK_URL = "https://ai-made-simple-portal.onrender.com/stripe/webhook"
TEST_EMAIL = "rick.test+webhooktest@gmail.com"

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")

if not STRIPE_WEBHOOK_SECRET:
    sys.exit("STRIPE_WEBHOOK_SECRET not set in .env -- can't sign a payload Stripe would accept")
if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    sys.exit("SUPABASE_URL / SUPABASE_SERVICE_KEY not set in .env -- can't verify the resulting row")


def sign_payload(payload_bytes, secret, timestamp=None):
    """Stripe's documented signing scheme: HMAC-SHA256 over "{t}.{payload}"."""
    timestamp = timestamp or int(time.time())
    signed_payload = f"{timestamp}.{payload_bytes.decode()}".encode()
    signature = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={signature}"


def build_fake_event(session_id):
    now = int(time.time())
    return {
        "id": f"evt_test_{uuid.uuid4().hex[:16]}",
        "object": "event",
        "api_version": "2023-10-16",
        "created": now,
        "livemode": False,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": session_id,
                "object": "checkout.session",
                "customer": "cus_test_webhooktest",
                "customer_details": {
                    "email": TEST_EMAIL,
                    "name": "Webhook Test",
                },
                "customer_email": TEST_EMAIL,
                "payment_status": "paid",
                "status": "complete",
                "amount_total": 8700,
                "currency": "usd",
            }
        },
    }


def post_fake_event(session_id):
    event = build_fake_event(session_id)
    # json.dumps output must be the EXACT bytes we sign -- requests would
    # re-serialize a dict passed via json=, so send raw bytes via data=.
    payload_bytes = json.dumps(event).encode()
    signature_header = sign_payload(payload_bytes, STRIPE_WEBHOOK_SECRET)

    resp = requests.post(
        WEBHOOK_URL,
        data=payload_bytes,
        headers={
            "Content-Type": "application/json",
            "Stripe-Signature": signature_header,
        },
        timeout=120,  # Render free-tier cold start can take 30-60s+
    )
    return resp


def fetch_user(email):
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/portal_users",
        params={"email": f"eq.{email}", "select": "*"},
        headers={
            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            "apikey": SUPABASE_SERVICE_KEY,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def delete_test_user(email):
    resp = requests.delete(
        f"{SUPABASE_URL}/rest/v1/portal_users",
        params={"email": f"eq.{email}"},
        headers={
            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            "apikey": SUPABASE_SERVICE_KEY,
            "Prefer": "return=representation",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def main():
    if "--cleanup" in sys.argv:
        deleted = delete_test_user(TEST_EMAIL)
        print(f"deleted {len(deleted)} row(s) for {TEST_EMAIL}")
        return

    before = fetch_user(TEST_EMAIL)
    print(f"rows for {TEST_EMAIL} before: {len(before)}")

    session_id = f"cs_test_{uuid.uuid4().hex[:16]}"
    print(f"\nPOSTing signed checkout.session.completed (session {session_id}) ...")
    resp = post_fake_event(session_id)
    print(f"response: {resp.status_code} {resp.text[:300]}")

    after = fetch_user(TEST_EMAIL)
    print(f"\nrows for {TEST_EMAIL} after: {len(after)}")
    if after:
        row = after[0]
        print(f"  id={row.get('id')} is_enrolled={row.get('is_enrolled')} "
              f"has_password_hash={bool(row.get('password_hash'))} "
              f"created_at={row.get('created_at')}")

    print("\nRun this script again (same command, no args) to verify idempotency --")
    print("row count for this email should stay the same, not double.")


if __name__ == "__main__":
    main()
