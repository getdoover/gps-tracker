from types import SimpleNamespace

import pytest

from gps_tracker.application import LOCATION_CHANNEL, GpsTrackerApplication


class Value:
    def __init__(self, value):
        self.value = value


def make_config(**overrides):
    values = {
        "latitude_path": "$io_state.latitude",
        "longitude_path": "$io_state.longitude",
        "altitude_path": "$io_state.altitude",
        "satellites_path": "$io_state.satellites",
        "hdop_path": "$io_state.hdop",
        "fix_status_path": "$io_state.gps_fix",
        "gps_time_path": "$io_state.gps_time",
        "min_satellites": None,
        "max_hdop": None,
        "reference_latitude": None,
        "reference_longitude": None,
        "bearing_offset_deg": 0.0,
        "notify_on_move": False,
        "move_alert_distance_m": 500.0,
        "location_min_move_m": 2.0,
    }
    values.update(overrides)
    return SimpleNamespace(**{k: Value(v) for k, v in values.items()})


class FakeTag:
    def __init__(self, value=None):
        self.value = value
        self.writes = 0

    def get(self):
        return self.value

    async def set(self, value):
        self.value = value
        self.writes += 1


TAG_NAMES = [
    "latitude",
    "longitude",
    "altitude",
    "satellites",
    "hdop",
    "fix_ok",
    "last_fix_ts",
    "bearing_deg",
    "distance_m",
    "fix_quality",
    "published_latitude",
    "published_longitude",
    "moved_away",
]


class FakeApi:
    def __init__(self):
        self.aggregates = []
        self.messages = []

    async def update_channel_aggregate(self, channel, data, replace_data=False, **kw):
        self.aggregates.append((channel, data, replace_data))

    async def create_message(self, channel, data, **kw):
        self.messages.append((channel, data))


class FakeNotification:
    def __init__(self):
        self.sent = []

    async def send(self, message=None, **kw):
        self.sent.append(message)


async def make_app(**config):
    app = object.__new__(GpsTrackerApplication)
    app.config = make_config(**config)
    app.tags = SimpleNamespace(**{name: FakeTag() for name in TAG_NAMES})
    app.api = FakeApi()
    app.notifications = SimpleNamespace(moved_away=FakeNotification())
    await app.setup()
    return app


def event(data, channel="io_state"):
    return SimpleNamespace(
        channel=SimpleNamespace(name=channel), message=SimpleNamespace(data=data)
    )


GOOD = {
    "latitude": -27.5,
    "longitude": 151.9,
    "altitude": 410.2,
    "satellites": 9,
    "hdop": 0.9,
    "gps_fix": "3D",
}


async def test_good_fix_publishes_tags_and_location():
    app = await make_app()
    await app.on_message_create(event({**GOOD, "gps_time": 1_795_050_000}))
    t = app.tags
    assert (t.latitude.value, t.longitude.value, t.altitude.value) == (
        -27.5,
        151.9,
        410.2,
    )
    assert (t.satellites.value, t.hdop.value, t.fix_ok.value) == (9, 0.9, True)
    assert t.last_fix_ts.value == 1_795_050_000_000
    assert t.fix_quality.value == "Good (9 satellites, HDOP 0.9)"
    assert t.bearing_deg.value is None and t.distance_m.value is None
    channel, data, replace = app.api.aggregates[0]
    assert channel == LOCATION_CHANNEL and replace is True
    assert data["lat"] == -27.5 and data["long"] == 151.9 and data["alt"] == 410.2
    assert app.api.messages == [(LOCATION_CHANNEL, data)]


async def test_no_data_does_nothing():
    app = await make_app(
        reference_latitude=-27.5, reference_longitude=151.9, notify_on_move=True
    )
    for data in ({}, {"pump_running": True}, None):
        await app.on_message_create(event(data))
    await app.on_message_create(event(GOOD, channel="ui_cmds"))
    assert all(getattr(app.tags, n).writes == 0 for n in TAG_NAMES)
    assert app.api.aggregates == [] and app.api.messages == []
    assert app.notifications.moved_away.sent == []


async def test_missing_optional_paths_and_values():
    app = await make_app(
        altitude_path="",
        satellites_path=None,
        hdop_path="  ",
        fix_status_path="",
        gps_time_path="",
    )
    await app.on_message_create(event({"latitude": "-27.5", "longitude": "151.9"}))
    assert app.tags.latitude.value == -27.5
    assert app.tags.fix_quality.value == "Good"
    assert app.tags.altitude.writes == 0
    assert app.tags.last_fix_ts.value > 1_700_000_000_000


async def test_bad_config_never_raises():
    app = await make_app(latitude_path="latitude")
    await app.on_message_create(event(GOOD))
    app = await make_app(longitude_path="$other.longitude")
    await app.on_message_create(event(GOOD))
    assert app.tags.latitude.writes == 0


@pytest.mark.parametrize(
    "data, config, reason",
    [
        ({**GOOD, "gps_fix": 0}, {}, "no fix"),
        ({**GOOD, "satellites": 3}, {"min_satellites": 5}, "satellites"),
        ({**GOOD, "hdop": 6.0}, {"max_hdop": 5.0}, "HDOP"),
        ({**GOOD, "latitude": 0, "longitude": 0}, {}, "no valid position"),
        ({"satellites": 0, "gps_fix": False}, {}, "no fix"),
        ({"satellites": 4}, {}, "no position"),
    ],
)
async def test_bad_fix_is_ignored(data, config, reason):
    app = await make_app(**config)
    app.tags.latitude.value = -27.4  # last good fix stays
    await app.on_message_create(event(data))
    assert app.tags.fix_ok.value is False
    assert reason in app.tags.fix_quality.value
    assert app.tags.latitude.value == -27.4
    assert app.api.aggregates == []


async def test_location_jitter_not_republished():
    app = await make_app(location_min_move_m=5.0)
    await app.on_message_create(event(GOOD))
    await app.on_message_create(event({**GOOD, "latitude": -27.50001}))  # ~1 m
    assert len(app.api.messages) == 1
    assert app.tags.latitude.value == -27.50001  # tags still follow every fix
    await app.on_message_create(event({**GOOD, "latitude": -27.5001}))  # ~11 m
    assert len(app.api.messages) == 2


async def test_bearing_and_distance_from_reference():
    app = await make_app(
        reference_latitude=-27.5, reference_longitude=151.9, bearing_offset_deg=10.0
    )
    await app.on_message_create(
        event({**GOOD, "latitude": -27.499, "longitude": 151.9})
    )
    assert app.tags.bearing_deg.value == pytest.approx(10.0, abs=0.05)
    assert app.tags.distance_m.value == pytest.approx(111.2, abs=0.5)


async def test_moved_away_notifies_once_and_rearms():
    app = await make_app(
        reference_latitude=-27.5,
        reference_longitude=151.9,
        notify_on_move=True,
        move_alert_distance_m=200.0,
    )
    near = {**GOOD, "latitude": -27.5005}  # ~56 m
    far = {**GOOD, "latitude": -27.505}  # ~556 m
    await app.on_message_create(event(near))
    assert app.notifications.moved_away.sent == []
    await app.on_message_create(event(far))
    await app.on_message_create(event({**far, "latitude": -27.506}))
    assert len(app.notifications.moved_away.sent) == 1
    assert "556 m" in app.notifications.moved_away.sent[0]
    await app.on_message_create(event(near))
    await app.on_message_create(event(far))
    assert len(app.notifications.moved_away.sent) == 2


async def test_no_notification_when_disabled_or_no_reference():
    app = await make_app(
        reference_latitude=-27.5, reference_longitude=151.9, move_alert_distance_m=10.0
    )
    await app.on_message_create(event({**GOOD, "latitude": -27.6}))
    app2 = await make_app(notify_on_move=True, move_alert_distance_m=10.0)
    await app2.on_message_create(event({**GOOD, "latitude": -27.6}))
    assert (
        app.notifications.moved_away.sent == []
        and app2.notifications.moved_away.sent == []
    )
