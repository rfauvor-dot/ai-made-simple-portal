"""Stripe webhook: on checkout.session.completed, create the student account
(idempotent on email) and email them their login credentials.

Render must set STRIPE_WEBHOOK_SECRET to the signing secret for the endpoint
registered in the Stripe dashboard as https://<render-url>/stripe/webhook.
"""
import json
import logging
import secrets

import stripe
from flask import Blueprint, request, jsonify

import config
from auth import hash_password
from db import db, User
from email_service import send_welcome_email

logger = logging.getLogger(__name__)

stripe_bp = Blueprint("stripe_webhook", __name__)


def _generate_temp_password():
    return secrets.token_urlsafe(9)  # ~12 chars, URL-safe


def handle_checkout_completed(session):
    """Idempotent: repeat webhook deliveries or repeat payments by the same
    email must not create duplicate accounts or re-send credentials for an
    already-enrolled student.
    """
    email = (session.get("customer_details") or {}).get("email") or session.get("customer_email")
    if not email:
        logger.error("checkout.session.completed with no customer email: %s", session.get("id"))
        return None
    email = email.strip().lower()

    existing = User.query.filter(User.email.ilike(email)).first()
    if existing:
        logger.info("Checkout completed for already-enrolled user %s -- skipping account creation", email)
        return existing

    temp_password = _generate_temp_password()
    name = (session.get("customer_details") or {}).get("name")
    user = User(
        email=email,
        password_hash=hash_password(temp_password),
        name=name,
        is_enrolled=True,
        stripe_customer_id=session.get("customer"),
        stripe_checkout_session=session.get("id"),
    )
    db.session.add(user)
    db.session.commit()

    send_welcome_email(email, temp_password, dry_run=False)
    logger.info("Enrolled new user %s from checkout session %s", email, session.get("id"))
    return user


@stripe_bp.route("/stripe/webhook", methods=["POST"])
def webhook():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature", "")

    if not config.STRIPE_WEBHOOK_SECRET:
        logger.error("STRIPE_WEBHOOK_SECRET not configured -- rejecting webhook")
        return jsonify({"error": "webhook not configured"}), 500

    try:
        # construct_event's only job here is signature verification -- its
        # return value is a stripe.Event of nested StripeObjects, which
        # support attribute/[] access but NOT .get(), so handle_checkout_completed
        # (and its self-test below) would break on the very first real,
        # correctly-signed request. Parse our own plain-dict copy of the
        # already-verified payload instead.
        stripe.Webhook.construct_event(payload, sig_header, config.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        logger.warning("Rejected webhook: %s", exc)
        return jsonify({"error": "invalid signature"}), 400

    event = json.loads(payload)
    if event.get("type") == "checkout.session.completed":
        handle_checkout_completed(event["data"]["object"])

    return jsonify({"received": True}), 200


def _sign(payload_bytes, secret):
    """Stripe's documented signing scheme, same as test_webhook.py -- used
    here so the self-test exercises the REAL signature-verified HTTP path,
    not just handle_checkout_completed() with a hand-fed plain dict. A
    hand-fed dict is exactly what let a real bug (construct_event returns
    StripeObjects, which don't support .get()) ship without being caught.
    """
    import hashlib
    import hmac
    import time

    timestamp = int(time.time())
    signed_payload = f"{timestamp}.{payload_bytes.decode()}".encode()
    signature = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={signature}"


if __name__ == "__main__":
    # Synthetic self-test against a Flask app context + in-memory sqlite,
    # posting a REALLY signed payload through the actual /stripe/webhook
    # route (not calling handle_checkout_completed directly) so this catches
    # anything that breaks between construct_event's output and what that
    # function expects.
    from flask import Flask

    config.STRIPE_WEBHOOK_SECRET = "whsec_test_fake_secret_for_selftest"

    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    db.init_app(app)
    app.register_blueprint(stripe_bp)

    fake_event = {
        "id": "evt_test_123",
        "object": "event",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_123",
                "customer": "cus_test_123",
                "customer_email": "STUDENT@Example.com",
                "customer_details": {"email": "STUDENT@Example.com", "name": "Test Student"},
            }
        },
    }
    payload_bytes = json.dumps(fake_event).encode()
    signature = _sign(payload_bytes, config.STRIPE_WEBHOOK_SECRET)

    with app.app_context():
        db.create_all()

    client = app.test_client()
    resp1 = client.post(
        "/stripe/webhook",
        data=payload_bytes,
        headers={"Content-Type": "application/json", "Stripe-Signature": signature},
    )
    assert resp1.status_code == 200, f"expected 200, got {resp1.status_code}: {resp1.text}"

    with app.app_context():
        assert User.query.count() == 1
        user1 = User.query.first()
        assert user1.email == "student@example.com"

    # Repeat delivery of the same event must not create a duplicate --
    # sign fresh (a real timestamp) but same email, same as a Stripe retry.
    signature2 = _sign(payload_bytes, config.STRIPE_WEBHOOK_SECRET)
    resp2 = client.post(
        "/stripe/webhook",
        data=payload_bytes,
        headers={"Content-Type": "application/json", "Stripe-Signature": signature2},
    )
    assert resp2.status_code == 200

    with app.app_context():
        assert User.query.count() == 1

    # An unsigned/garbage signature must be rejected, not silently accepted.
    resp3 = client.post(
        "/stripe/webhook",
        data=payload_bytes,
        headers={"Content-Type": "application/json", "Stripe-Signature": "t=1,v1=garbage"},
    )
    assert resp3.status_code == 400

    print("stripe_webhook.py self-test passed")
