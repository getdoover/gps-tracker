"""Pure GPS helpers: parsing raw readings, judging a fix, and the bearing and
distance from a reference point. Nothing here touches Doover, so it is what the
tests exercise directly."""

import math
from datetime import UTC, datetime
from typing import Any

EARTH_RADIUS_M = 6_371_008.8  # mean Earth radius (IUGG)

# Fix-status strings that mean "no fix". Anything else that is not empty reads as
# a fix: "3D", "2D", "A" (NMEA active), "fix", "dgps", "rtk", ...
_NO_FIX_STRINGS = {
    "",
    "0",
    "false",
    "no",
    "none",
    "no fix",
    "nofix",
    "no_fix",
    "invalid",
    "v",  # NMEA RMC "void"
    "off",
    "lost",
}

# Below this an epoch number is seconds, above it milliseconds (1e11 s is the
# year 5138; 1e11 ms is March 1973).
_EPOCH_MS_THRESHOLD = 1e11


def parse_path(value: Any) -> tuple[str, list[str]] | None:
    """Split a message path '$channel.path.to.value' into (channel, [path]).

    Returns None for an empty or missing path (the optional inputs are switched
    off by clearing them). Raises ValueError (TypeError for a non-string) for a
    path that is set but malformed.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("A message path must be a string like '$channel.key'.")
    path = value.strip()
    if not path:
        return None
    if not path.startswith("$"):
        raise ValueError(f"Message path {path!r} must start with '$channel'.")

    body = path[1:]
    if ":" in body:
        channel, raw_path = body.split(":", 1)
    elif "." in body:
        channel, raw_path = body.split(".", 1)
    else:
        raise ValueError(f"Message path {path!r} needs a value path after the channel.")

    channel = channel.strip()
    parts = [part.strip() for part in raw_path.split(".") if part.strip()]
    if not channel or not parts:
        raise ValueError(
            f"Message path {path!r} needs both a channel and a value path."
        )
    return channel, parts


def extract(data: Any, path: list[str]) -> Any:
    """The value at `path` in a message's data, or None if any step is missing."""
    value = data
    for part in path:
        if isinstance(value, dict):
            value = value.get(part)
        elif isinstance(value, list):
            try:
                value = value[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
        if value is None:
            return None
    return value


def to_float(value: Any) -> float | None:
    """A finite number from a raw reading (numbers or numeric strings), else None."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def to_fix_status(value: Any) -> bool | None:
    """Read a raw fix-status value. None when there is no reading.

    Booleans are taken as-is; numbers are a fix when above zero (NMEA GGA fix
    quality 1-8, gpsd mode 2/3); strings are a fix unless they say otherwise.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value > 0
    if isinstance(value, str):
        text = value.strip().lower()
        number = to_float(text)
        if number is not None:
            return number > 0
        return text not in _NO_FIX_STRINGS
    return None


def to_epoch_ms(value: Any) -> int | None:
    """A GPS time as milliseconds since the epoch.

    Accepts epoch seconds or milliseconds (numbers or numeric strings) and ISO
    8601 strings (a trailing 'Z' or no zone reads as UTC). None if unreadable.
    """
    if value is None or isinstance(value, bool):
        return None
    number = to_float(value)
    if number is not None:
        if number <= 0:
            return None
        return int(number if number >= _EPOCH_MS_THRESHOLD else number * 1000)
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return int(parsed.timestamp() * 1000)
    return None


def valid_coordinates(lat: float | None, lon: float | None) -> bool:
    """In range, and not the 0,0 'null island' a receiver reports with no fix."""
    if lat is None or lon is None:
        return False
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return False
    return not (lat == 0.0 and lon == 0.0)


def fix_rejection(
    *,
    fix_status: bool | None,
    satellites: float | None,
    hdop: float | None,
    min_satellites: int | None,
    max_hdop: float | None,
) -> str | None:
    """Why a fix should be ignored, or None if it is good enough to use.

    A quality reading the source does not send is not held against it: the
    minimum-satellites and maximum-HDOP checks only apply when there is a value
    to check.
    """
    if fix_status is False:
        return "receiver reports no fix"
    if (
        min_satellites is not None
        and satellites is not None
        and satellites < min_satellites
    ):
        return f"{satellites:g} satellites (minimum {min_satellites})"
    if max_hdop is not None and hdop is not None and hdop > max_hdop:
        return f"HDOP {hdop:g} (maximum {max_hdop:g})"
    return None


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle (haversine) distance in metres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def bearing_deg(
    lat1: float, lon1: float, lat2: float, lon2: float, offset_deg: float = 0.0
) -> float:
    """Initial bearing from point 1 to point 2, in degrees.

    0 is true North, increasing clockwise (90 East, 180 South, 270 West), plus
    `offset_deg`, normalised into [0, 360).
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_lambda = math.radians(lon2 - lon1)
    x = math.sin(d_lambda) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(
        d_lambda
    )
    bearing = math.degrees(math.atan2(x, y)) + (offset_deg or 0.0)
    bearing %= 360.0
    # -0.0 % 360 and values a hair under 360 round to 360.0; keep it in range.
    return 0.0 if bearing >= 360.0 or bearing == 0.0 else bearing
