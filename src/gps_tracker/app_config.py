from pathlib import Path

from pydoover import config
from pydoover.config import ApplicationPosition
from pydoover.processor import ManySubscriptionConfig

_PATH_HELP = (
    " Leave blank to use this input's automatic address, which the edge bridge "
    "fills in. Or give a message path, e.g. '$io_state.x'."
)


class GpsTrackerConfig(config.Schema):
    # -- inputs (raw GPS fields, by message path) ---------------------------
    latitude_path = config.String(
        "Latitude Message Path",
        name="latitude_path",
        description="Latitude in decimal degrees." + _PATH_HELP,
        default="",
        position=1,
    )
    longitude_path = config.String(
        "Longitude Message Path",
        name="longitude_path",
        description=(
            "Longitude in decimal degrees. Must be on the same channel as the "
            "latitude, so both come from the same message." + _PATH_HELP
        ),
        default="",
        position=2,
    )
    altitude_path = config.String(
        "Altitude Message Path",
        name="altitude_path",
        description="Altitude in metres." + _PATH_HELP,
        default="",
        position=3,
    )
    satellites_path = config.String(
        "Satellites Message Path",
        name="satellites_path",
        description="Number of satellites in use." + _PATH_HELP,
        default="",
        position=4,
    )
    hdop_path = config.String(
        "HDOP Message Path",
        name="hdop_path",
        description=(
            "Horizontal dilution of precision (HDOP); lower is better." + _PATH_HELP
        ),
        default="",
        position=5,
    )
    fix_status_path = config.String(
        "Fix Status Message Path",
        name="fix_status_path",
        description=(
            "The receiver's fix status: true/false, a fix quality number (0 = no "
            "fix), or text such as '3D' or 'no fix'. A reading of no fix is ignored."
            + _PATH_HELP
        ),
        default="",
        position=6,
    )
    gps_time_path = config.String(
        "GPS Time Message Path",
        name="gps_time_path",
        description=(
            "Time of the fix, as epoch seconds or milliseconds or an ISO 8601 "
            "string. Without it, the time the message arrived is used." + _PATH_HELP
        ),
        default="",
        position=7,
    )

    # -- quality filter ------------------------------------------------------
    min_satellites = config.Integer(
        "Minimum Satellites",
        name="min_satellites",
        description=(
            "Ignore fixes from fewer satellites than this. Leave empty for no minimum. "
            "Only applies when the source sends a satellite count."
        ),
        default=None,
        position=10,
    )
    max_hdop = config.Number(
        "Maximum HDOP",
        name="max_hdop",
        description=(
            "Ignore fixes with an HDOP above this (for example 5.0). Leave empty for no "
            "maximum. Only applies when the source sends an HDOP."
        ),
        default=None,
        position=11,
    )

    # -- reference point -----------------------------------------------------
    reference_latitude = config.Number(
        "Reference Latitude",
        name="reference_latitude",
        description=(
            "Latitude of a fixed reference point in decimal degrees, such as a pivot "
            "centre or a home yard. With the reference longitude set, the bearing and "
            "distance from this point are published. Leave empty for none."
        ),
        default=None,
        position=20,
    )
    reference_longitude = config.Number(
        "Reference Longitude",
        name="reference_longitude",
        description="Longitude of the reference point in decimal degrees. Leave empty for none.",
        default=None,
        position=21,
    )
    bearing_offset_deg = config.Number(
        "Bearing Offset",
        name="bearing_offset_deg",
        description=(
            "Degrees added to the bearing from the reference point (0 = North, "
            "clockwise). Use it to line the bearing up with a machine's own zero, "
            "for example a pivot whose 0° is not true North."
        ),
        default=0.0,
        position=22,
    )

    # -- notification --------------------------------------------------------
    notify_on_move = config.Boolean(
        "Notify When Moved Away",
        name="notify_on_move",
        description=(
            "Send a notification when a good fix is further than the alert distance "
            "from the reference point. Needs a reference point. Sent once each time "
            "it moves out; it re-arms when a fix is back inside."
        ),
        default=False,
        position=30,
    )
    move_alert_distance_m = config.Number(
        "Alert Distance",
        name="move_alert_distance_m",
        description="Distance from the reference point, in metres, beyond which the notification is sent.",
        default=500.0,
        position=31,
        show_if=notify_on_move,
    )

    # -- advanced ------------------------------------------------------------
    location_min_move_m = config.Number(
        "Location Update Distance",
        name="location_min_move_m",
        description=(
            "The device's map location (and its location history) is only updated "
            "when a fix has moved at least this many metres from the last one "
            "published, so GPS jitter on a parked machine does not fill its track. "
            "0 publishes every good fix."
        ),
        default=2.0,
        advanced=True,
        position=40,
    )
    subscription = ManySubscriptionConfig(
        default=["io_state"],
        advanced=True,
        position=41,
    )

    position = ApplicationPosition(position=42)


def export():
    GpsTrackerConfig.export(
        Path(__file__).parents[2] / "doover_config.json",
        "gps_tracker",
    )
