"""The modules import and the published schemas build."""


def test_import_handler():
    from gps_tracker import handler
    from gps_tracker.application import GpsTrackerApplication

    assert handler and GpsTrackerApplication


def test_config_schema_keys():
    from gps_tracker.app_config import GpsTrackerConfig

    schema = GpsTrackerConfig.to_schema()
    props = schema["properties"]
    for key in (
        "latitude_path",
        "longitude_path",
        "reference_latitude",
        "dv_proc_subscriptions",
    ):
        assert key in props
    # Blank: read from the input's automatic address.
    for key in (
        "latitude_path",
        "longitude_path",
        "altitude_path",
        "satellites_path",
        "hdop_path",
        "fix_status_path",
        "gps_time_path",
    ):
        assert props[key]["default"] == ""
        assert "automatic address" in props[key]["description"]
    assert props["dv_proc_subscriptions"]["default"] == ["io_state"]


def test_notifications_schema():
    from gps_tracker.app_notifications import GpsTrackerNotifications

    assert set(GpsTrackerNotifications().to_schema()) == {"moved_away"}
