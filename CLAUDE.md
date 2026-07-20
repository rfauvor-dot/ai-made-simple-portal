# CLAUDE.md

Guidance for Claude Code working in this repository.

## What this is

The members-only course portal for the "AI Made Simple 40+" offer, separate
from the `ai-made-simple-landing` repo (the public landing page + Stripe
checkout, deployed to Render as its own service). This repo is the payment
wall: Stripe fires a webhook here, an account is created, and the student
logs in to watch 8 module videos and download 8 printable PDFs.

Videos are unlisted YouTube uploads, not Supabase Storage -- the Supabase
project's global file-size cap (50MB) can't hold 200-320MB course videos.
See the storage note below.

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

Production (Render): `gunicorn app:app` (see `Procfile`), never `python app.py` --
`app.run(debug=True)` is dev-only and is never invoked when gunicorn imports
the `app` object directly. `gunicorn` doesn't run on Windows (no `os.fork`),
so this can only be exercised for real on Render's Linux environment, not
locally on this machine.

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
- **Videos are unlisted YouTube embeds; PDFs are private Supabase Storage.**
  Supabase's project-level file-size cap is 50MB, well under the 200-320MB
  of each module video (confirmed by probing bucket creation with a 500MB
  `file_size_limit`, which was rejected) — raising it requires a paid plan
  change Rick hasn't made, so videos live on YouTube instead.
  `lessons_config.LESSONS[i]["youtube_id"]` is the 11-character ID from each
  video's URL, filled in by hand after uploading through YouTube Studio (as
  **unlisted**, not public) — `youtube_embed_url()` turns it into a
  `youtube-nocookie.com/embed/...` iframe src. Until a lesson's `youtube_id`
  is set, its page shows a "video coming soon" placeholder instead of a
  broken embed.
  PDFs are tiny (~150KB each) and fit fine in Supabase — `storage.py`
  generates short-lived signed URLs against the private `lesson-pdfs`
  bucket at request time. `upload_lessons.py` creates that bucket and
  uploads all 8 PDFs from `Desktop\Modules 1-8 Printable Scripts` (already
  run once; safe to re-run, it upserts).
- **`DATABASE_URL` unset → sqlite fallback, by design.** `config.py` defaults
  to a local `local_dev.db` file so the app boots and templates/routes are
  testable without real Supabase credentials. Render **must** set
  `DATABASE_URL` to the Supabase Postgres connection string, and
  `schema.sql` must be applied there first (Supabase SQL editor) — SQLAlchemy
  does not manage migrations here, `db.create_all()` is a no-op once the
  table already exists.
- **`DATABASE_URL` must be Supabase's POOLED connection string, not the
  direct one.** Confirmed via `test_webhook.py` against production: the
  direct connection (`db.<ref>.supabase.co:5432`) is IPv6-only in many
  Supabase regions, and Render's networking can't reach it — the webhook
  hung for ~30s then 500'd with no row ever written. The pooled/Supavisor
  string (Project Settings → Database → Connection pooling → Transaction
  mode, `aws-0-<region>.pooler.supabase.com:6543`, username
  `postgres.<project-ref>`) works from Render. See `.env.example`.
- **Email sending defaults to dry-run.** `email_service.send_welcome_email`
  only sends for real if `SENDGRID_API_KEY` is set AND `dry_run=False` is
  passed explicitly (the webhook handler does pass `dry_run=False` — the
  gate is really "is a key configured", same pattern as
  `marketing-platform/senders.py`). Sending a real student's temporary
  password to the wrong place is a real harm, not just an API cost.
- **Passwords are emailed once, in plaintext, by design of the brief.**
  There's no forced password-reset-on-first-login flow — if that's wanted
  later it's a small addition to `auth.py`, not built yet.

## Deploying to Render

Claude has no Render account, no Stripe dashboard access, and no Supabase
Postgres password (only the Storage API service_role key) — every step
below has to be done by Rick directly, not automated from this repo.

1. **Render → New → Web Service**, connect GitHub repo
   `rfauvor-dot/ai-made-simple-portal`, branch `master`.
2. Build command: `pip install -r requirements.txt`. Start command:
   `gunicorn app:app` (Render should auto-detect this from `Procfile`, but
   set it explicitly if it doesn't).
3. Set these environment variables in Render's dashboard (values come from
   Supabase/Stripe/SendGrid dashboards, not from this repo — see
   `.env.example` for the full list and format):
   `SECRET_KEY` (generate a random one, don't reuse the local dev default),
   `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`,
   `SUPABASE_PDF_BUCKET`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`,
   `SENDGRID_API_KEY`, `FROM_EMAIL`, `FROM_NAME`, `PORTAL_BASE_URL` (set to
   the real `https://<service>.onrender.com` URL once Render assigns it).
4. **Apply `schema.sql` in the Supabase SQL editor** (project
   `tsxhuzsanoqahsrbumxz`) before the first deploy — `db.create_all()` in
   `app.py` is a no-op once the table exists, it doesn't run migrations.
5. In the Stripe dashboard (or the `ai-made-simple-landing` repo's checkout
   config), point the webhook endpoint at
   `https://<service>.onrender.com/stripe/webhook`, subscribed to
   `checkout.session.completed`. Copy the signing secret it gives you into
   `STRIPE_WEBHOOK_SECRET` above.
6. Test with Stripe's `4242 4242 4242 4242` test card end-to-end: checkout →
   webhook fires → account created in `portal_users` → welcome email
   arrives → log in → lessons/PDFs load.

## Not yet done / explicitly out of scope

- No password-reset / "forgot password" flow.
- No admin UI for managing enrollments or lesson content — both are static
  (`lessons_config.py`) or manual (Supabase dashboard).
- No refund/un-enroll handling on the webhook side (only
  `checkout.session.completed` is handled).
