import os
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

# Shared timezone utilities for call metadata and recording.

TIMEZONE_ENV_VAR = "TIMEZONE"


def get_timezone_name() -> str:
    """Return the timezone name from the TIMEZONE env var, or empty string.

    When empty, callers should treat it as "use local time".
    """
    tz_env = os.getenv(TIMEZONE_ENV_VAR, "").strip()
    return tz_env


def get_timezone() -> Optional[ZoneInfo]:
    """Return a ZoneInfo instance for the configured timezone, or None.

    If TIMEZONE is unset or invalid, return None so callers can
    fall back to naive local datetimes.
    """
    tz_name = get_timezone_name()
    if not tz_name:
        return None

    try:
        return ZoneInfo(tz_name)
    except Exception:
        return None


def format_timestamp(ts: float) -> str:
    """Format a UNIX timestamp into a human-readable string with timezone.

    Respects the TIMEZONE env var when valid, otherwise uses local time.
    """
    try:
        tz = get_timezone()
        if tz is not None:
            dt = datetime.fromtimestamp(ts, tz)
        else:
            dt = datetime.fromtimestamp(ts)
        return dt.strftime("%Y-%m-%d %H:%M:%S %Z")
    except Exception:
        return ""
