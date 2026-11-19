from pydoover import ui

from .app_tags import GpsTrackerTags


class GpsTrackerUI(ui.UI):
    # The device's position itself shows on the device page and organisation
    # map, from the location channel this app publishes to. These are the
    # numbers behind it.
    last_fix = ui.Timestamp(
        "Last Fix",
        value=GpsTrackerTags.last_fix_ts,
        label_format="D MMM YYYY h:mma ({relative})",
        position=1,
    )
    fix_ok = ui.BooleanVariable("GPS Fix", value=GpsTrackerTags.fix_ok, position=2)
    fix_quality = ui.TextVariable(
        "Fix Quality", value=GpsTrackerTags.fix_quality, position=3
    )

    bearing = ui.NumericVariable(
        "Bearing From Reference",
        name="bearing",
        units="°",
        value=GpsTrackerTags.bearing_deg,
        precision=1,
        position=10,
        hidden=True,
    )
    distance = ui.NumericVariable(
        "Distance From Reference",
        name="distance",
        units="m",
        value=GpsTrackerTags.distance_m,
        precision=1,
        position=11,
        hidden=True,
    )

    latitude = ui.NumericVariable(
        "Latitude", units="°", value=GpsTrackerTags.latitude, precision=6, position=20
    )
    longitude = ui.NumericVariable(
        "Longitude", units="°", value=GpsTrackerTags.longitude, precision=6, position=21
    )
    altitude = ui.NumericVariable(
        "Altitude", units="m", value=GpsTrackerTags.altitude, precision=1, position=22
    )
    satellites = ui.NumericVariable(
        "Satellites", value=GpsTrackerTags.satellites, precision=0, position=23
    )
    hdop = ui.NumericVariable(
        "HDOP",
        value=GpsTrackerTags.hdop,
        precision=1,
        position=24,
        ranges=[
            ui.Range("Good", 0, 2, ui.Colour.green),
            ui.Range("Fair", 2, 5, ui.Colour.yellow),
            ui.Range("Poor", 5, 20, ui.Colour.red),
        ],
    )

    async def setup(self):
        # Bearing and distance only mean something against a reference point.
        if has_reference_point(self.config):
            self.bearing.hidden = False
            self.distance.hidden = False


def has_reference_point(config) -> bool:
    if config is None:
        return False
    lat = getattr(config, "reference_latitude", None)
    lon = getattr(config, "reference_longitude", None)
    return (
        lat is not None
        and lon is not None
        and lat.value is not None
        and lon.value is not None
    )


def export():
    from pathlib import Path

    GpsTrackerUI(None, None, None).export(
        Path(__file__).parents[2] / "doover_config.json",
        "gps_tracker",
    )
