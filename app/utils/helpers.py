"""Validation and formatting helpers used by the routes."""

import re
from datetime import date, datetime, time

REGISTER_RE = re.compile(r"^[A-Za-z0-9/_-]{4,30}$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{3,64}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
SUBJECT_CODE_RE = re.compile(r"^[A-Za-z0-9-]{2,20}$")


class ValidationError(Exception):
    """Raised by the validate_* helpers; routes turn it into a flash message."""


def clean(value):
    return (value or "").strip()


# ----------------------------------------------------------------------
# Field validation
# ----------------------------------------------------------------------
def validate_name(value, field="Name"):
    value = clean(value)
    if len(value) < 2 or len(value) > 120:
        raise ValidationError("{} must be between 2 and 120 characters.".format(field))
    if not re.match(r"^[A-Za-z .'-]+$", value):
        raise ValidationError("{} may contain only letters, spaces, dots and hyphens.".format(field))
    return value


def validate_register_number(value):
    value = clean(value).upper()
    if not REGISTER_RE.match(value):
        raise ValidationError(
            "Register number must be 4-30 characters (letters, digits, - _ / only)."
        )
    return value


def validate_username(value):
    value = clean(value).lower()
    if not USERNAME_RE.match(value):
        raise ValidationError(
            "Username must be 3-64 characters using letters, digits, dot, underscore or hyphen."
        )
    return value


def validate_email(value, required=False):
    value = clean(value)
    if not value:
        if required:
            raise ValidationError("Email is required.")
        return None
    if not EMAIL_RE.match(value):
        raise ValidationError("Enter a valid email address.")
    return value.lower()


def validate_password(value, required=True):
    value = value or ""
    if not value:
        if required:
            raise ValidationError("Password is required.")
        return None
    if len(value) < 6:
        raise ValidationError("Password must be at least 6 characters long.")
    return value


def validate_subject_code(value):
    value = clean(value).upper()
    if not SUBJECT_CODE_RE.match(value):
        raise ValidationError("Subject code must be 2-20 letters, digits or hyphens.")
    return value


def validate_subject_name(value):
    value = clean(value)
    if len(value) < 2 or len(value) > 120:
        raise ValidationError("Subject name must be between 2 and 120 characters.")
    return value


def validate_int(value, field, minimum=None, maximum=None, default=None):
    value = clean(str(value)) if value is not None else ""
    if value == "" and default is not None:
        return default
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValidationError("{} must be a whole number.".format(field))
    if minimum is not None and number < minimum:
        raise ValidationError("{} must be at least {}.".format(field, minimum))
    if maximum is not None and number > maximum:
        raise ValidationError("{} must not be greater than {}.".format(field, maximum))
    return number


def validate_float(value, field, minimum=None, maximum=None, default=None):
    value = clean(str(value)) if value is not None else ""
    if value == "" and default is not None:
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValidationError("{} must be a number.".format(field))
    if minimum is not None and number < minimum:
        raise ValidationError("{} must be at least {}.".format(field, minimum))
    if maximum is not None and number > maximum:
        raise ValidationError("{} must not be greater than {}.".format(field, maximum))
    return number


def parse_date(value, field="Date", default=None):
    value = clean(value)
    if not value:
        if default is not None:
            return default
        raise ValidationError("{} is required.".format(field))
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise ValidationError("{} must look like 2026-09-15.".format(field))


def parse_time(value, field="Time", default=None):
    value = clean(value)
    if not value:
        if default is not None:
            return default
        raise ValidationError("{} is required.".format(field))
    for pattern in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(value, pattern).time()
        except ValueError:
            continue
    raise ValidationError("{} must look like 09:00.".format(field))


# ----------------------------------------------------------------------
# Formatting
# ----------------------------------------------------------------------
def percent(part, whole, digits=2):
    """Safe percentage helper - never divides by zero."""
    if not whole:
        return 0.0
    return round((float(part) / float(whole)) * 100.0, digits)


def fmt_time(value):
    if isinstance(value, datetime):
        return value.strftime("%I:%M %p")
    if isinstance(value, time):
        return value.strftime("%I:%M %p")
    return "-"


def fmt_date(value):
    if isinstance(value, (datetime, date)):
        return value.strftime("%d %b %Y")
    return "-"


def status_badge(status):
    """Bootstrap colour for an attendance status."""
    return {
        "PRESENT": "success",
        "LATE": "warning",
        "ABSENT": "danger",
        "REVIEW_REQUIRED": "secondary",
    }.get(status, "secondary")
