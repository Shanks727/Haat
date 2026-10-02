"""E-mail / SMS notification service (architecture: external service).
If no SMTP server is configured, messages are written to the log instead."""
import smtplib
from email.message import EmailMessage

from flask import current_app


def send_email(to, subject, body):
    cfg = current_app.config
    if not cfg.get("MAIL_SERVER"):
        current_app.logger.info("[mail] to=%s subject=%s\n%s", to, subject, body)
        return False
    msg = EmailMessage()
    msg["From"] = cfg["MAIL_FROM"]
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=10) as smtp:
            smtp.starttls()
            if cfg.get("MAIL_USERNAME"):
                smtp.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
            smtp.send_message(msg)
        return True
    except Exception as exc:  # never break checkout because mail failed
        current_app.logger.warning("Mail to %s failed: %s", to, exc)
        return False


def order_status_mail(order):
    store = current_app.config["STORE_NAME"]
    lines = [f"Hi {order.user.name},", "",
             f"Your order {order.number} is now: {order.status}.", "",
             "Items:"]
    lines += [f"  {i.quantity} x {i.product.name}" for i in order.items]
    lines += ["", f"Total: Rs. {order.total_amount}", "", f"Thanks for shopping with {store}."]
    send_email(order.user.email, f"{store}: order {order.number} {order.status.lower()}",
               "\n".join(lines))
