"""Stripe webhook: on checkout.session.completed, create the student account
(idempotent on email) and email them their login credentials.

Render must set STRIPE_WEBHOOK_SECRET to the signing secret for the endpoint
registered in the Stripe dashboard as https://<render-url>/stripe/webhook.
"""
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
        event = stripe.Webhook.construct_event(payload, sig_header, config.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        logger.warning("Rejected webhook: %s", exc)
        return jsonify({"error": "invalid signature"}), 400

    if event["type"] == "checkout.session.completed":
        handle_checkout_completed(event["data"]["object"])

    return jsonify({"received": True}), 200


if __name__ == "__main__":
    # Synthetic self-test against a Flask app context + in-memory sqlite,
    # bypassing the real Stripe signature check (no live webhook secret here).
    from flask import Flask

    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    db.init_app(app)

    fake_session = {
        "id": "cs_test_123",
        "customer": "cus_test_123",
        "customer_email": "STUDENT@Example.com",
        "customer_details": {"email": "STUDENT@Example.com", "name": "Test Student"},
    }

    with app.app_context():
        db.create_all()
        user1 = handle_checkout_completed(fake_session)
        assert user1.email == "student@example.com"
        assert User.query.count() == 1

        # Repeat delivery of the same event must not create a duplicate.
        user2 = handle_checkout_completed(fake_session)
        assert user2.id == user1.id
        assert User.query.count() == 1

    print("stripe_webhook.py self-test passed")
