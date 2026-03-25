#!/usr/bin/env python3
"""
Optional SMTP email delivery for ShadowRealms AI.
Uses only the Python standard library (smtplib).
"""

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import List, Optional

logger = logging.getLogger(__name__)


def _truthy(val: Optional[str]) -> bool:
    if val is None:
        return False
    return str(val).strip().lower() in ("1", "true", "yes", "on")


def is_smtp_configured() -> bool:
    host = os.environ.get("SMTP_HOST", "").strip()
    from_addr = os.environ.get("SMTP_FROM", "").strip()
    return bool(host and from_addr)


def _send_raw(to_addrs: List[str], subject: str, body: str) -> bool:
    if not to_addrs:
        logger.warning("mail_service: no recipients; skip send")
        return False
    if not is_smtp_configured():
        logger.info("mail_service: SMTP not configured; skip send")
        return False

    host = os.environ.get("SMTP_HOST", "").strip()
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "").strip()
    from_addr = os.environ.get("SMTP_FROM", "").strip()
    use_tls = _truthy(os.environ.get("SMTP_USE_TLS", "true"))
    use_ssl = _truthy(os.environ.get("SMTP_USE_SSL", "false"))

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_addrs)
    msg.set_content(body)

    try:
        if use_ssl or port == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=context, timeout=30) as smtp:
                if user and password:
                    smtp.login(user, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as smtp:
                smtp.ehlo()
                if use_tls:
                    context = ssl.create_default_context()
                    smtp.starttls(context=context)
                    smtp.ehlo()
                if user and password:
                    smtp.login(user, password)
                smtp.send_message(msg)
        logger.info("mail_service: sent mail to %s subject=%s", to_addrs, subject)
        return True
    except Exception as e:
        logger.error("mail_service: failed to send mail: %s", e)
        return False


def send_welcome_registration(to_email: str, username: str, password_plain: str) -> bool:
    app_name = os.environ.get("APP_PUBLIC_NAME", "ShadowRealms AI").strip()
    body = f"""Welcome to {app_name}

Your account has been created successfully.

Username: {username}
Email: {to_email}
Password: {password_plain}

Please sign in and change your password if you wish.

— {app_name}
"""
    return _send_raw([to_email], f"Welcome to {app_name}", body)


def send_invalid_invite_alert(
    admin_email: str,
    *,
    attempted_code: str,
    username: str,
    email: str,
    remote_addr: Optional[str],
) -> bool:
    app_name = os.environ.get("APP_PUBLIC_NAME", "ShadowRealms AI").strip()
    body = f"""[{app_name}] Invalid invite code attempt

Someone tried to register with an invalid or exhausted invite code.

Attempted code: {attempted_code}
Username (submitted): {username}
Email (submitted): {email}
IP: {remote_addr or "unknown"}

Review user moderation / security logs as needed.

— {app_name} (automated)
"""
    return _send_raw([admin_email], f"[{app_name}] Invalid invite signup attempt", body)
