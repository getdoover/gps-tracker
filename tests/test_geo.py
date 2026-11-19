import math

import pytest

from gps_tracker import geo


def test_parse_path():
    assert geo.parse_path("$io_state.latitude") == ("io_state", ["latitude"])
    assert geo.parse_path("$io_state.gps.0.lat") == ("io_state", ["gps", "0", "lat"])
    assert geo.parse_path("$io_state:gps.lat") == ("io_state", ["gps", "lat"])
    assert geo.parse_path("") is None
    assert geo.parse_path("   ") is None
    assert geo.parse_path(None) is None
    for bad in ("io_state.latitude", "$io_state", "$.lat"):
        with pytest.raises(ValueError):
            geo.parse_path(bad)


def test_extract():
    data = {"gps": {"fixes": [{"lat": -27.5}]}}
    assert geo.extract(data, ["gps", "fixes", "0", "lat"]) == -27.5
    assert geo.extract(data, ["gps", "missing"]) is None
    assert geo.extract(data, ["gps", "fixes", "3", "lat"]) is None


def test_to_float():
    assert geo.to_float("12.5") == 12.5
    assert geo.to_float(3) == 3.0
    for bad in (None, True, "abc", float("nan"), float("inf"), {}):
        assert geo.to_float(bad) is None


@pytest.mark.parametrize(
    "raw, expected",
    [
        (True, True),
        (False, False),
        (0, False),
        (1, True),
        (3, True),
        ("3D", True),
        ("2d", True),
        ("A", True),
        ("V", False),
        ("no fix", False),
        ("0", False),
        ("1", True),
        ("", False),
        (None, None),
    ],
)
def test_fix_status(raw, expected):
    assert geo.to_fix_status(raw) is expected


def test_epoch_ms():
    assert geo.to_epoch_ms(1_795_050_000) == 1_795_050_000_000
    assert geo.to_epoch_ms(1_795_050_000_123) == 1_795_050_000_123
    assert geo.to_epoch_ms("1795050000") == 1_795_050_000_000
    assert geo.to_epoch_ms("2026-11-19T00:00:00Z") == 1_795_046_400_000
    assert geo.to_epoch_ms("2026-11-19T10:00:00+10:00") == 1_795_046_400_000
    assert geo.to_epoch_ms("2026-11-19T00:00:00") == 1_795_046_400_000
    for bad in (None, 0, -5, "yesterday", True):
        assert geo.to_epoch_ms(bad) is None


def test_valid_coordinates():
    assert geo.valid_coordinates(-27.5, 151.9)
    assert not geo.valid_coordinates(0.0, 0.0)
    assert not geo.valid_coordinates(91.0, 10.0)
    assert not geo.valid_coordinates(10.0, -181.0)
    assert not geo.valid_coordinates(None, 10.0)


def test_fix_rejection():
    ok = dict(fix_status=True, satellites=9, hdop=0.9, min_satellites=5, max_hdop=3.0)
    assert geo.fix_rejection(**ok) is None
    assert geo.fix_rejection(**{**ok, "fix_status": False}) == "receiver reports no fix"
    assert "satellites" in geo.fix_rejection(**{**ok, "satellites": 3})
    assert "HDOP" in geo.fix_rejection(**{**ok, "hdop": 4.2})
    # Missing quality readings are not held against the fix.
    assert (
        geo.fix_rejection(
            fix_status=None, satellites=None, hdop=None, min_satellites=5, max_hdop=2.0
        )
        is None
    )
    # No filter configured.
    assert (
        geo.fix_rejection(
            fix_status=None, satellites=1, hdop=20, min_satellites=None, max_hdop=None
        )
        is None
    )


# A point near Toowoomba; 0.001° of latitude is ~111 m.
REF = (-27.5, 151.9)


def _offset(d_north_m: float, d_east_m: float):
    lat = REF[0] + math.degrees(d_north_m / geo.EARTH_RADIUS_M)
    lon = REF[1] + math.degrees(
        d_east_m / (geo.EARTH_RADIUS_M * math.cos(math.radians(REF[0])))
    )
    return lat, lon


@pytest.mark.parametrize(
    "north, east, bearing",
    [
        (300, 0, 0.0),
        (0, 300, 90.0),
        (-300, 0, 180.0),
        (0, -300, 270.0),
        (300, 300, 45.0),
        (-300, -300, 225.0),
    ],
)
def test_bearing_cardinal(north, east, bearing):
    lat, lon = _offset(north, east)
    assert geo.bearing_deg(*REF, lat, lon) == pytest.approx(bearing, abs=0.05)


def test_bearing_offset_wraps():
    lat, lon = _offset(0, -300)  # due West, 270
    assert geo.bearing_deg(*REF, lat, lon, offset_deg=100) == pytest.approx(
        10.0, abs=0.05
    )
    assert geo.bearing_deg(*REF, lat, lon, offset_deg=-280) == pytest.approx(
        350.0, abs=0.05
    )
    north = _offset(300, 0)
    assert 0.0 <= geo.bearing_deg(*REF, *north, offset_deg=360) < 360.0


def test_distance():
    lat, lon = _offset(300, 400)
    assert geo.distance_m(*REF, lat, lon) == pytest.approx(500.0, rel=1e-3)
    assert geo.distance_m(*REF, *REF) == 0.0
