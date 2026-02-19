# app/email.py
import os
import resend
from app.config import settings

resend.api_key = settings.RESEND_API_KEY

EMAIL_TEMPLATES = {
    "payment_failed_day0": {
        "subject": "Action Required: Your payment failed",
        "body": lambda ctx: f"""
Hi there,

We tried to charge your card ${ctx['amount']:.2f} but the payment didn't go through.

This happens — expired cards, bank holds, insufficient funds. It's a quick fix.

👉 Update your payment method here: {ctx['link']}

If you don't update within 3 days, your account may be paused.

— The Team
"""
    },
    "payment_failed_day3": {
        "subject": "Reminder: Your payment is still outstanding",
        "body": lambda ctx: f"""
Hi there,

Just a reminder — your payment of ${ctx['amount']:.2f} is still outstanding.

👉 Update your payment method: {ctx['link']}

Your account will be suspended in 4 days if not resolved.

— The Team
"""
    },
    "payment_failed_day7": {
        "subject": "Final Notice: Account suspension in 24 hours",
        "body": lambda ctx: f"""
Hi there,

This is your final notice. Your payment of ${ctx['amount']:.2f} has been outstanding for 7 days.

👉 Resolve now to keep your account active: {ctx['link']}

After 24 hours, your account will be suspended.

— The Team
"""
    },
}

async def send_email(to_email: str, subject: str, template_name: str, context: dict):
    """
    Send email via Resend. Falls back to console log if no API key configured.
    """
    if not settings.RESEND_API_KEY or settings.RESEND_API_KEY == "re_mock":
        # Fallback: log to console (dev mode)
        print(f"\n📧 === EMAIL (DEV MODE - not sent) ===")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print(f"Template: {template_name}")
        print(f"Context: {context}")
        print(f"=====================================\n")
        return True

    template = EMAIL_TEMPLATES.get(template_name)
    if not template:
        print(f"Unknown template: {template_name}")
        return False

    body = template["body"](context)

    try:
        params = {
            "from": settings.FROM_EMAIL,
            "to": [to_email],
            "subject": subject,
            "text": body,
        }
        resend.Emails.send(params)
        print(f"📧 Email sent to {to_email}: {subject}")
        return True
    except Exception as e:
        print(f"❌ Email failed: {e}")
        return False
