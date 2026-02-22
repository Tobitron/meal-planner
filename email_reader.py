"""Read ingredient request and meal plan reply emails from Gmail inbox."""

import email
import email.message
import imaplib
import logging
import os
import re

from config import (
    GMAIL_APP_PASSWORD_ENV,
    GMAIL_AUTHORIZED_SENDERS,
    GMAIL_INGREDIENT_KEYWORD,
    GMAIL_REPLY_SUBJECT_PREFIX,
    GMAIL_SENDER,
    IMAP_HOST,
    IMAP_PORT,
)

log = logging.getLogger(__name__)


def fetch_ingredient_requests() -> list:
    """Fetch unread ingredient request emails and return their subjects.

    Searches for unread emails from authorized senders containing the
    ingredient keyword in the subject. Marks matched emails as read.
    Returns empty list on any failure (non-fatal).
    """
    try:
        password = os.environ.get(GMAIL_APP_PASSWORD_ENV)
        if not password:
            log.warning(f"No app password found in {GMAIL_APP_PASSWORD_ENV}, skipping ingredient emails")
            return []

        subjects = []
        with imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT) as imap:
            imap.login(GMAIL_SENDER, password)
            imap.select("INBOX")

            for sender in GMAIL_AUTHORIZED_SENDERS:
                search_criteria = f'(UNSEEN FROM "{sender}" SUBJECT "{GMAIL_INGREDIENT_KEYWORD}")'
                _, data = imap.search(None, search_criteria)
                if not data or not data[0]:
                    continue

                msg_ids = data[0].split()
                for msg_id in msg_ids:
                    _, msg_data = imap.fetch(msg_id, "(BODY[HEADER.FIELDS (SUBJECT)])")
                    if not msg_data or not msg_data[0]:
                        continue

                    raw_header = msg_data[0][1]
                    if isinstance(raw_header, bytes):
                        raw_header = raw_header.decode("utf-8", errors="replace")

                    subject = ""
                    for line in raw_header.splitlines():
                        if line.lower().startswith("subject:"):
                            subject = line[8:].strip()
                            break

                    if subject:
                        subjects.append(subject)
                        imap.store(msg_id, "+FLAGS", "\\Seen")
                        log.info(f"Found ingredient request: {subject!r}")

        return subjects

    except Exception as e:
        log.warning(f"Could not read ingredient emails: {e}")
        return []


def _strip_quoted_text(body: str) -> str:
    """Strip quoted original message from a reply email body."""
    lines = body.splitlines()
    cleaned = []
    for line in lines:
        # Stop at "On ... wrote:" attribution line
        if re.match(r"^On .+ wrote:$", line):
            break
        # Stop at "--- Original Message" divider
        if re.match(r"^-+\s*Original Message", line, re.IGNORECASE):
            break
        # Stop at quoted lines
        if line.startswith(">"):
            break
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def _get_text_body(msg: email.message.Message) -> str:
    """Extract plain text body from an email message."""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
    return ""


def fetch_meal_plan_replies() -> list[str]:
    """Fetch unread replies to meal plan emails and return their body text.

    Searches for unread emails from authorized senders with subject
    matching the reply prefix. Strips quoted original text from bodies.
    Marks matched emails as read. Returns empty list on any failure.
    """
    try:
        password = os.environ.get(GMAIL_APP_PASSWORD_ENV)
        if not password:
            log.warning(f"No app password found in {GMAIL_APP_PASSWORD_ENV}, skipping reply emails")
            return []

        bodies = []
        with imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT) as imap:
            imap.login(GMAIL_SENDER, password)
            imap.select("INBOX")

            for sender in GMAIL_AUTHORIZED_SENDERS:
                search_criteria = f'(UNSEEN FROM "{sender}" SUBJECT "{GMAIL_REPLY_SUBJECT_PREFIX}")'
                _, data = imap.search(None, search_criteria)
                if not data or not data[0]:
                    continue

                msg_ids = data[0].split()
                for msg_id in msg_ids:
                    _, msg_data = imap.fetch(msg_id, "(RFC822)")
                    if not msg_data or not msg_data[0]:
                        continue

                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)
                    body = _get_text_body(msg)
                    body = _strip_quoted_text(body)

                    if body:
                        bodies.append(body)
                        imap.store(msg_id, "+FLAGS", "\\Seen")
                        log.info(f"Found meal plan reply: {body[:100]!r}")
                    else:
                        log.warning("Found reply email but could not extract body text")
                        imap.store(msg_id, "+FLAGS", "\\Seen")

        return bodies

    except Exception as e:
        log.warning(f"Could not read meal plan reply emails: {e}")
        return []
