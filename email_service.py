"""SendGrid welcome-email sender. Defaults to dry-run (logs only, nothing
sent) unless SENDGRID_API_KEY is configured AND dry_run=False is passed
explicitly -- same gate already used for real sends in
marketing-platform/senders.py and stock-platform/mean_reversion_trader.py.
Sending real credentials to the wrong address is a real harm, not just an
API cost, so this stays opt-in rather than opt-out.
"""
import logging

import config

logger = logging.getLogger(__name__)


def send_welcome_email(to_email, temp_password, dry_run=True):
    subject = "Welcome to AI Made Simple 40+ -- your login details"
    body_text = (
        f"You're enrolled!\n\n"
        f"Login at {config.PORTAL_BASE_URL}/login\n"
        f"Email: {to_email}\n"
        f"Temporary password: {temp_password}\n\n"
        f"We recommend changing your password after your first login."
    )

    if dry_run or not config.SENDGRID_API_KEY:
        logger.info("[DRY RUN] Welcome email to %s:\n%s", to_email, body_text)
        return {"dry_run": True, "to": to_email}

    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail

    message = Mail(
        from_email=(config.FROM_EMAIL, config.FROM_NAME),
        to_emails=to_email,
        subject=subject,
        plain_text_content=body_text,
    )
    try:
        client = SendGridAPIClient(config.SENDGRID_API_KEY)
        response = client.send(message)
        return {"dry_run": False, "to": to_email, "status_code": response.status_code}
    except Exception as exc:
        # The account was already created before this runs (see
        # stripe_webhook.handle_checkout_completed) -- a bad/placeholder
        # SendGrid key must not turn that success into a 500 that makes
        # Stripe think webhook delivery itself failed and keep retrying.
        # Log it loudly and let the caller decide the account creation was
        # still the success that matters.
        logger.error("Welcome email to %s failed to send: %s", to_email, exc)
        return {"dry_run": False, "to": to_email, "error": str(exc)}


if __name__ == "__main__":
    result = send_welcome_email("student@example.com", "temp-pw-123", dry_run=True)
    assert result["dry_run"] is True
    assert result["to"] == "student@example.com"

    # A bad key / send failure must return an error dict, never raise --
    # this is exactly what broke production before it was caught: the real
    # webhook route doesn't (and shouldn't have to) wrap this call in its
    # own try/except.
    import sendgrid

    config.SENDGRID_API_KEY = "placeholder_invalid_key"
    original_client = sendgrid.SendGridAPIClient

    class _FailingClient:
        def __init__(self, *a, **kw):
            pass

        def send(self, *a, **kw):
            raise RuntimeError("simulated SendGrid failure (invalid key)")

    sendgrid.SendGridAPIClient = _FailingClient
    try:
        result = send_welcome_email("student@example.com", "temp-pw-123", dry_run=False)
        assert result["dry_run"] is False
        assert "error" in result
    finally:
        sendgrid.SendGridAPIClient = original_client

    print("email_service.py self-test passed")
