# CLAUDE.md

Guidance for Claude Code working in this repository.

## What this is

The members-only course portal for the "AI Made Simple 40+" offer, separate
from the `ai-made-simple-landing` repo (the public landing page + Stripe
checkout, deployed to Render as its own service). This repo is the payment
wall: Stripe fires a webhook here, an account is created, and the student
logs in to watch 8 module videos and download 8 printable PDFs.

Sibling projects on this machine (`forex-platform`, `stock-platform`,
`marketing-platform`) follow the same conventions used here: no
`requirements.txt`-free approach (this repo does have one), env-var-only
config, dry-run-by-default for anything that sends a real message, and
`if __name__ == "__main__"` synthetic self-tests instead of a pytest suite.

## Commands

```
pip install -r requirements.txt
python app.py                # http://localhost:5000, sqlite fallback if DATABASE_URL unset
```

Self-tests (no pytest suite -- run directly):
```
python config.py
python lessons_config.py
python storage.py
python auth.py
python email_service.py
python stripe_webhook.py
```

## Architecture notes

- **Two separate repos, one funnel.** `ai-made-simple-landing` (Stripe
  Checkout + marketing site) and this repo (post-payment portal) are
  deployed as two independent Render services. The only link between them
  is the Stripe webhook: the landing repo's Checkout Session points its
  webhook endpoint at `https://<this-service>.onrender.com/stripe/webhook`.
- **No signup route, on purpose.** Accounts are created exclusively by
  `stripe_webhook.handle_checkout_completed` on `checkout.session.completed`.
  There is no `/register` — access is payment-gated, full stop.
- **Idempotent by email, not by Stripe event ID.** Repeat webhook deliveries
  (Stripe retries) or a second payment from the same email must not create a
  duplicate account or re-send credentials — `handle_checkout_completed`
  checks `User.query.filter(User.email.ilike(email))` first and no-ops if
  found. If duplicate-payment refund handling is ever needed, it isn't built
  yet.
- **Videos/PDFs are never committed to git or served from Render's disk.**
  The 8 module videos alone are ~200MB each (~2GB total) — `storage.py`
  generates short-lived signed URLs against private Supabase Storage buckets
  (`lesson-videos`, `lesson-pdfs`) at request time. Upload the actual files
  to those buckets from the Supabase dashboard using the exact filenames in
  `lessons_config.py` (e.g. `Module 1 Video.mp4`) — nothing in this repo
  uploads them for you.
- **`DATABASE_URL` unset → sqlite fallback, by design.** `config.py` defaults
  to a local `local_dev.db` file so the app boots and templates/routes are
  testable without real Supabase credentials. Render **must** set
  `DATABASE_URL` to the Supabase Postgres connection string, and
  `schema.sql` must be applied there first (Supabase SQL editor) — SQLAlchemy
  does not manage migrations here, `db.create_all()` is a no-op once the
  table already exists.
- **Email sending defaults to dry-run.** `email_service.send_welcome_email`
  only sends for real if `SENDGRID_API_KEY` is set AND `dry_run=False` is
  passed explicitly (the webhook handler does pass `dry_run=False` — the
  gate is really "is a key configured", same pattern as
  `marketing-platform/senders.py`). Sending a real student's temporary
  password to the wrong place is a real harm, not just an API cost.
- **Passwords are emailed once, in plaintext, by design of the brief.**
  There's no forced password-reset-on-first-login flow — if that's wanted
  later it's a small addition to `auth.py`, not built yet.

## Not yet done / explicitly out of scope

- No password-reset / "forgot password" flow.
- No admin UI for managing enrollments or lesson content — both are static
  (`lessons_config.py`) or manual (Supabase dashboard).
- No refund/un-enroll handling on the webhook side (only
  `checkout.session.completed` is handled).
- Video/PDF files themselves are **not** in this repo — see the Supabase
  Storage note above. They still need to be uploaded from
  `Desktop\AI made simple 40 plus Modules` and
  `Desktop\Modules 1-8 Printable Scripts` on this machine.
