"""Email notification for finished automation jobs.

After a scheduled / headless run, send the recipients a short message with
*links* (not attachments) to the report outputs: the PDF, the PowerPoint, and
the folder of per-wafer PNGs. The outputs are expected to live on a shared
drive, so each link is both a raw path (copy-paste into Explorer) and a
``file://`` URL.

SMTP settings come from the environment so credentials never live in the
``.wtjob`` file (which is committed / scheduled):

    WAFERTOOL_EMAIL_BACKEND   outlook | smtp    (default: outlook if the
                                                 Outlook COM bridge is available,
                                                 else smtp)
    WAFERTOOL_SMTP_HOST       mail server host           (required for smtp)
    WAFERTOOL_SMTP_PORT       port                       (default 25)
    WAFERTOOL_SMTP_USER       login user                 (optional)
    WAFERTOOL_SMTP_PASSWORD   login password             (optional)
    WAFERTOOL_SMTP_FROM       From: address              (default: user@host)
    WAFERTOOL_SMTP_SECURITY   none | starttls | ssl      (default inferred
                                                          from port: 465->ssl,
                                                          587->starttls,
                                                          else none)

The ``outlook`` backend sends through the locally installed Outlook using the
signed-in profile (e.g. a corporate mailbox), so no SMTP host or password is
needed. Outlook must be able to run for the message to leave the Outbox.

Recipients come from the job's ``email_to`` list.
"""
from __future__ import annotations

import os
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formatdate
from html import escape
from pathlib import Path

from ..logger import log

__all__ = ["Report", "SmtpConfig", "smtp_config_from_env",
           "send_report_email", "send_test_email", "send_via_outlook",
           "select_backend", "EmailNotConfigured"]


class EmailNotConfigured(RuntimeError):
    """Raised when email is requested but WAFERTOOL_SMTP_HOST is not set."""


@dataclass
class Report:
    """One report's linkable outputs (a job may produce several, e.g. per EFF
    parameter). Each path is optional: an empty string means "do not include
    this link"; a non-file string (e.g. a 'not generated' message) is shown as
    not generated; an existing file/folder is linked."""
    label: str
    pdf: str = ""
    pptx: str = ""
    folder: str = ""


@dataclass
class SmtpConfig:
    host: str
    port: int = 25
    user: str = ""
    password: str = ""
    sender: str = ""
    security: str = "none"        # none | starttls | ssl


def _infer_security(port: int) -> str:
    if port == 465:
        return "ssl"
    if port == 587:
        return "starttls"
    return "none"


def smtp_config_from_env() -> SmtpConfig | None:
    """Build an SmtpConfig from environment variables, or None if no host set."""
    host = os.environ.get("WAFERTOOL_SMTP_HOST", "").strip()
    if not host:
        return None
    try:
        port = int(os.environ.get("WAFERTOOL_SMTP_PORT", "").strip() or 25)
    except ValueError:
        port = 25
    user = os.environ.get("WAFERTOOL_SMTP_USER", "").strip()
    security = os.environ.get("WAFERTOOL_SMTP_SECURITY", "").strip().lower() \
        or _infer_security(port)
    sender = os.environ.get("WAFERTOOL_SMTP_FROM", "").strip() \
        or user or f"wafertool@{host}"
    return SmtpConfig(
        host=host,
        port=port,
        user=user,
        password=os.environ.get("WAFERTOOL_SMTP_PASSWORD", ""),
        sender=sender,
        security=security,
    )


def _as_link(path: str) -> str | None:
    """A ``file://`` URL for an existing file/folder, or None if it is missing
    or is a placeholder message rather than a real path."""
    if not path:
        return None
    if not (os.path.isfile(path) or os.path.isdir(path)):
        return None
    try:
        return Path(path).resolve().as_uri()
    except (ValueError, OSError):
        return None


def _display_path(path: str) -> str:
    """The absolute form of *path* for display, so a relative out_dir still
    yields a copy-pastable location. Falls back to the raw string."""
    try:
        return str(Path(path).resolve())
    except (ValueError, OSError):
        return path


def _text_body(reports: list[Report]) -> str:
    lines: list[str] = ["Wafer report generation finished.", ""]
    for r in reports:
        lines.append(r.label)
        for name, path in (("PDF", r.pdf),
                           ("PPTX", r.pptx),
                           ("Output folder", r.folder)):
            if not path:
                continue   # link type not requested for this job
            link = _as_link(path)
            if link:
                lines.append(f"  {name}: {_display_path(path)}")
                lines.append(f"        {link}")
            else:
                lines.append(f"  {name}: (not generated)")
        lines.append("")
    return "\n".join(lines)


def _html_body(reports: list[Report]) -> str:
    blocks: list[str] = ["<p>Wafer report generation finished.</p>"]
    for r in reports:
        rows: list[str] = []
        for name, path in (("PDF", r.pdf),
                           ("PPTX", r.pptx),
                           ("Output folder", r.folder)):
            if not path:
                continue   # link type not requested for this job
            link = _as_link(path)
            if link:
                rows.append(
                    f"<li><b>{escape(name)}:</b> "
                    f'<a href="{escape(link, quote=True)}">'
                    f"{escape(_display_path(path))}</a></li>"
                )
            else:
                rows.append(f"<li><b>{escape(name)}:</b> "
                            "<i>not generated</i></li>")
        blocks.append(f"<h4>{escape(r.label)}</h4><ul>{''.join(rows)}</ul>")
    return f"<html><body>{''.join(blocks)}</body></html>"


# ── backend selection ─────────────────────────────────────────────────────────

def _outlook_available() -> bool:
    try:
        import win32com.client  # noqa: F401
        return True
    except Exception:
        return False


def select_backend(explicit: str | None = None) -> str:
    """Resolve the email backend: 'outlook' or 'smtp'.

    Honours *explicit* / ``WAFERTOOL_EMAIL_BACKEND`` when set, otherwise prefers
    Outlook if its COM bridge is importable, falling back to SMTP.
    """
    choice = (explicit or os.environ.get("WAFERTOOL_EMAIL_BACKEND", "")).strip().lower()
    if choice in ("outlook", "smtp"):
        return choice
    return "outlook" if _outlook_available() else "smtp"


def send_via_outlook(recipients: list[str], subject: str, html_body: str) -> None:
    """Send one HTML email through the locally installed Outlook (signed-in
    profile). Requires pywin32 and a usable Outlook install."""
    import pythoncom
    import win32com.client as win32

    pythoncom.CoInitialize()          # safe on any thread; balances CoUninitialize
    try:
        app = win32.Dispatch("Outlook.Application")
        mail = app.CreateItem(0)      # 0 = olMailItem
        mail.To = "; ".join(recipients)
        mail.Subject = subject
        mail.HTMLBody = html_body
        mail.Send()
    finally:
        pythoncom.CoUninitialize()


def _smtp_send(cfg: SmtpConfig, msg: EmailMessage) -> None:
    if cfg.security == "ssl":
        smtp: smtplib.SMTP = smtplib.SMTP_SSL(
            cfg.host, cfg.port, context=ssl.create_default_context())
    else:
        smtp = smtplib.SMTP(cfg.host, cfg.port)
    try:
        if cfg.security == "starttls":
            smtp.starttls(context=ssl.create_default_context())
        if cfg.user:
            smtp.login(cfg.user, cfg.password)
        smtp.send_message(msg)
    finally:
        smtp.quit()


def send_report_email(
    recipients: list[str],
    subject: str,
    reports: list[Report],
    *,
    config: SmtpConfig | None = None,
    backend: str | None = None,
) -> None:
    """Send one notification email with links to *reports* outputs.

    Uses the Outlook backend (signed-in profile) or SMTP, per ``backend`` /
    ``WAFERTOOL_EMAIL_BACKEND``. Raises ``EmailNotConfigured`` if SMTP is chosen
    but no host is set, or the underlying transport error on failure. Callers in
    the automation layer catch these so a mail problem never fails a good report.
    """
    recipients = [r.strip() for r in recipients if r and r.strip()]
    if not recipients:
        return
    chosen = select_backend(backend)

    if chosen == "outlook":
        send_via_outlook(recipients, subject, _html_body(reports))
        log.info("Notification email sent to %s via Outlook", ", ".join(recipients))
        return

    cfg = config or smtp_config_from_env()
    if cfg is None:
        raise EmailNotConfigured(
            "email requested but WAFERTOOL_SMTP_HOST is not set")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg.sender
    msg["To"] = ", ".join(recipients)
    msg["Date"] = formatdate(localtime=True)
    msg.set_content(_text_body(reports))
    msg.add_alternative(_html_body(reports), subtype="html")
    _smtp_send(cfg, msg)
    log.info("Notification email sent to %s via SMTP", ", ".join(recipients))


def send_test_email(recipients: list[str], *, backend: str | None = None) -> str:
    """Send a small confirmation email so a user can verify delivery before
    scheduling. Returns the backend used ('outlook' or 'smtp')."""
    recipients = [r.strip() for r in recipients if r and r.strip()]
    if not recipients:
        raise ValueError("no recipients given")
    chosen = select_backend(backend)
    subject = "Wafer Map Tool — test email"
    html = ("<html><body><p>This is a <b>test email</b> from the Wafer Map Tool "
            "automation.</p><p>If you received this, report notifications are "
            "working on this machine.</p></body></html>")

    if chosen == "outlook":
        send_via_outlook(recipients, subject, html)
    else:
        cfg = smtp_config_from_env()
        if cfg is None:
            raise EmailNotConfigured(
                "email requested but WAFERTOOL_SMTP_HOST is not set")
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = cfg.sender
        msg["To"] = ", ".join(recipients)
        msg["Date"] = formatdate(localtime=True)
        msg.set_content("This is a test email from the Wafer Map Tool automation.")
        msg.add_alternative(html, subtype="html")
        _smtp_send(cfg, msg)
    log.info("Test email sent to %s via %s", ", ".join(recipients), chosen)
    return chosen
