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
    client = SendGridAPIClient(config.SENDGRID_API_KEY)
    response = client.send(message)
    return {"dry_run": False, "to": to_email, "status_code": response.status_code}


if __name__ == "__main__":
    result = send_welcome_email("student@example.com", "temp-pw-123", dry_run=True)
    assert result["dry_run"] is True
    assert result["to"] == "student@example.com"
    print("email_service.py self-test passed")
