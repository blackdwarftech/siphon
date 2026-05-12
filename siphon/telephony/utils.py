"""Telephony utility helpers."""

import re
from typing import Optional


def validate_phone_number(phone: Optional[str]) -> str:
    """Validate and normalize a phone number.

    Args:
        phone: Phone number string to validate.

    Returns:
        The normalized phone number.

    Raises:
        ValueError: If the phone number is empty, None, or contains invalid characters.
    """
    if not phone:
        raise ValueError("Phone number is required")

    # Strip common formatting characters
    normalized = phone.strip()

    if not normalized:
        raise ValueError("Phone number cannot be empty")

    # Basic character validation: digits, +, -, spaces, parentheses, dots
    # Reject anything that looks like path traversal or command injection
    if not re.match(r"^[\d\+\-\s\(\)\.]+$", normalized):
        raise ValueError(
            f"Invalid phone number format: {normalized}. "
            "Phone numbers may only contain digits, +, -, spaces, parentheses, and dots."
        )

    # Must contain at least some digits
    digits_only = re.sub(r"\D", "", normalized)
    if len(digits_only) < 7:
        raise ValueError(
            f"Phone number too short: {normalized}. "
            "Must contain at least 7 digits."
        )

    return normalized
