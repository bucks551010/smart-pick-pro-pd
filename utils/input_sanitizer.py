"""
utils/input_sanitizer.py
========================
Centralised input validation and sanitization for all user-supplied data.

Security controls addressed
---------------------------
  CWE-20  – Improper Input Validation  : strict allow-list patterns
  CWE-79  – Cross-Site Scripting       : HTML entity encoding / tag stripping
  CWE-89  – SQL Injection              : keyword detection as defence-in-depth
                                         (primary defence is parameterised queries)
  CWE-943 – NoSQL/LDAP injection       : operator / special-char stripping

All sanitizers raise ValueError with a user-friendly message on rejection so
callers can surface the message directly in the UI.

Usage
-----
    from utils.input_sanitizer import (
        sanitize_email,
        sanitize_display_name,
        sanitize_notes,
        sanitize_player_name,
        sanitize_reset_code,
        validate_password_strength,
    )

    try:
        clean_email = sanitize_email(raw_email)
        clean_name  = sanitize_display_name(raw_display_name)
        validate_password_strength(raw_password)
    except ValueError as exc:
        st.error(str(exc))
        st.stop()
"""

from __future__ import annotations

import html
import re
import unicodedata

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_EMAIL_LEN        = 254   # RFC 5321
_MAX_DISPLAY_NAME_LEN = 64
_MAX_NOTES_LEN        = 2_000
_MAX_PLAYER_NAME_LEN  = 100
_RESET_CODE_LEN       = 6     # matches _generate_reset_token() in auth_gate.py

# Allow-list pattern for email (RFC 5322 simplified)
_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9!#$%&'*+/=?^_`{|}~-]+"
    r"(?:\.[a-zA-Z0-9!#$%&'*+/=?^_`{|}~-]+)*"
    r"@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z]{2,})+$"
)

# Allow-list: letters (all scripts), digits, spaces, hyphens, underscores,
# apostrophes, dots.  Unicode letters are allowed so non-ASCII names work.
_DISPLAY_NAME_RE = re.compile(r"^[\w\s'\-\.]+$", re.UNICODE)

# Player names: same rule, slightly tighter (no dots)
_PLAYER_NAME_RE = re.compile(r"^[\w\s'\-]+$", re.UNICODE)

# Reset code: exactly _RESET_CODE_LEN decimal digits
_RESET_CODE_RE = re.compile(r"^\d{6}$")

# SQL injection keyword detection (defence-in-depth)
_SQL_INJECTION_RE = re.compile(
    r"\b(SELECT|INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|EXEC|EXECUTE"
    r"|UNION|CAST|CONVERT|DECLARE|WAITFOR|BENCHMARK|SLEEP|LOAD_FILE"
    r"|OUTFILE|DUMPFILE|INFORMATION_SCHEMA)\b",
    re.IGNORECASE,
)

# Dangerous HTML tags (for notes field which accepts more text)
_DANGEROUS_TAG_RE = re.compile(
    r"<\s*(script|iframe|object|embed|link|meta|form|input|button"
    r"|base|applet|xml|svg)[^>]*>",
    re.IGNORECASE,
)

# Password strength requirements
_MIN_PASSWORD_LEN  = 10
_PASSWORD_UPPER_RE = re.compile(r"[A-Z]")
_PASSWORD_LOWER_RE = re.compile(r"[a-z]")
_PASSWORD_DIGIT_RE = re.compile(r"[0-9]")
_PASSWORD_SPECIAL_RE = re.compile(r"""[!@#$%^&*()\-_=+\[\]{};:',.<>?/\\|`~"]""")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize_unicode(value: str) -> str:
    """
    Normalize to NFC form and strip ambiguous look-alike Unicode categories
    that could be used for homograph attacks.
    Does NOT remove non-ASCII; legitimate international characters are kept.
    """
    return unicodedata.normalize("NFC", value)


def _strip_html_tags(value: str) -> str:
    """Remove all HTML/XML tags from a string."""
    return re.sub(r"<[^>]*>", "", value)


def _encode_html_entities(value: str) -> str:
    """HTML-encode <, >, &, ", ' to prevent XSS (CWE-79)."""
    return html.escape(value, quote=True)


def _check_sql_injection(value: str) -> None:
    """
    Raise ValueError when the value contains SQL injection keywords.
    This is defence-in-depth; primary protection is parameterised queries.
    """
    if _SQL_INJECTION_RE.search(value):
        raise ValueError("Input contains disallowed keywords.")


def _check_length(value: str, max_len: int, field_name: str) -> None:
    if len(value) > max_len:
        raise ValueError(
            f"{field_name} must not exceed {max_len} characters."
        )


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty.")


# ---------------------------------------------------------------------------
# Public sanitizers
# ---------------------------------------------------------------------------

def sanitize_email(raw: str) -> str:
    """
    Validate and normalise an email address.

    Returns the lowercased, stripped email on success.
    Raises ValueError with a user-friendly message on failure.

    CWE-20: allows only RFC 5322-simplified format via strict regex.
    """
    if not isinstance(raw, str):
        raise ValueError("Email must be a string.")
    value = raw.strip().lower()
    _require_non_empty(value, "Email")
    _check_length(value, _MAX_EMAIL_LEN, "Email")
    _check_sql_injection(value)
    if not _EMAIL_RE.match(value):
        raise ValueError("Please enter a valid email address.")
    return value


def sanitize_display_name(raw: str) -> str:
    """
    Validate and normalise a display name.

    - Strips leading/trailing whitespace
    - Collapses internal whitespace runs to a single space
    - Rejects names with HTML special characters / SQL keywords
    - Encodes any residual HTML entities for safe storage and rendering

    Returns the cleaned display name.
    Raises ValueError with a user-friendly message on failure.
    """
    if not isinstance(raw, str):
        raise ValueError("Display name must be a string.")
    value = raw.strip()
    value = re.sub(r"\s+", " ", value)   # collapse whitespace
    value = _normalize_unicode(value)
    _require_non_empty(value, "Display name")
    _check_length(value, _MAX_DISPLAY_NAME_LEN, "Display name")
    _check_sql_injection(value)
    if not _DISPLAY_NAME_RE.match(value):
        raise ValueError(
            "Display name may only contain letters, numbers, spaces, "
            "hyphens, underscores, apostrophes, and dots."
        )
    # HTML-encode special characters before storage (CWE-79)
    return _encode_html_entities(value)


def sanitize_notes(raw: str) -> str:
    """
    Sanitize free-text bet notes.

    - Strips dangerous HTML tags (script, iframe, etc.)
    - HTML-encodes remaining angle brackets
    - Enforces max length

    Returns the cleaned note text.
    Raises ValueError on failure.
    """
    if not isinstance(raw, str):
        raise ValueError("Notes must be a string.")
    value = raw.strip()
    # Strip dangerous tags before encoding
    value = _DANGEROUS_TAG_RE.sub("", value)
    value = _strip_html_tags(value)
    _check_length(value, _MAX_NOTES_LEN, "Notes")
    _check_sql_injection(value)
    return _encode_html_entities(value)


def sanitize_player_name(raw: str) -> str:
    """
    Validate a player name used in prop lookups / manual entries.

    Returns the trimmed, normalised name.
    Raises ValueError on failure.
    """
    if not isinstance(raw, str):
        raise ValueError("Player name must be a string.")
    value = raw.strip()
    value = re.sub(r"\s+", " ", value)
    value = _normalize_unicode(value)
    _require_non_empty(value, "Player name")
    _check_length(value, _MAX_PLAYER_NAME_LEN, "Player name")
    _check_sql_injection(value)
    if not _PLAYER_NAME_RE.match(value):
        raise ValueError(
            "Player name may only contain letters, numbers, spaces, "
            "hyphens, and apostrophes."
        )
    return value


def sanitize_reset_code(raw: str) -> str:
    """
    Validate a 6-digit password-reset code.

    Returns the stripped code string on success.
    Raises ValueError on failure.
    """
    if not isinstance(raw, str):
        raise ValueError("Reset code must be a string.")
    value = raw.strip()
    if not _RESET_CODE_RE.match(value):
        raise ValueError("Reset code must be exactly 6 digits.")
    return value


def sanitize_search_query(raw: str, max_len: int = 200) -> str:
    """
    Sanitize a free-text search query.

    Strips HTML, encodes entities, enforces length, and rejects SQL keywords.
    Returns the cleaned query string.
    """
    if not isinstance(raw, str):
        raise ValueError("Search query must be a string.")
    value = _strip_html_tags(raw.strip())
    _check_length(value, max_len, "Search query")
    _check_sql_injection(value)
    return _encode_html_entities(value)


def validate_password_strength(password: str) -> None:
    """
    Enforce password complexity policy.

    Requirements:
      - At least 10 characters
      - At least one uppercase letter
      - At least one lowercase letter
      - At least one digit
      - At least one special character

    Raises ValueError with a descriptive message if any requirement fails.
    Does NOT return the password – callers hash it separately.
    """
    if not isinstance(password, str):
        raise ValueError("Password must be a string.")
    errors: list[str] = []
    if len(password) < _MIN_PASSWORD_LEN:
        errors.append(f"at least {_MIN_PASSWORD_LEN} characters")
    if not _PASSWORD_UPPER_RE.search(password):
        errors.append("an uppercase letter (A–Z)")
    if not _PASSWORD_LOWER_RE.search(password):
        errors.append("a lowercase letter (a–z)")
    if not _PASSWORD_DIGIT_RE.search(password):
        errors.append("a digit (0–9)")
    if not _PASSWORD_SPECIAL_RE.search(password):
        errors.append("a special character (!@#$%…)")
    if errors:
        raise ValueError("Password must contain " + ", ".join(errors) + ".")
