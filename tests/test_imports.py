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
    assert props["latitude_path"]["default"] == "$io_state.latitude"
    assert props["dv_proc_subscriptions"]["default"] == ["io_state"]


def test_notifications_schema():
    from gps_tracker.app_notifications import GpsTrackerNotifications

    assert set(GpsTrackerNotifications().to_schema()) == {"moved_away"}
