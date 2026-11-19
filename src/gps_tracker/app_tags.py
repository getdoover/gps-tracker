from pydoover.tags import Tag, Tags


class GpsTrackerTags(Tags):
    # The last good fix. Peers read these (e.g. a pivot app reads bearing_deg).
    latitude = Tag("number", default=None)
    longitude = Tag("number", default=None)
    altitude = Tag("number", default=None)  # metres
    satellites = Tag("number", default=None)
    hdop = Tag("number", default=None)
    # Whether the latest reading was a usable fix (None until the first reading).
    fix_ok = Tag("boolean", default=None)
    # Time of the last good fix, ms since the epoch.
    last_fix_ts = Tag("number", default=None)
    # From the reference point; None while no reference point is configured.
    bearing_deg = Tag("number", default=None)  # 0 = North, clockwise, + offset
    distance_m = Tag("number", default=None)

    # Readable summary of the latest reading's quality, for the UI.
    fix_quality = Tag("string", default=None)
    # The position last written to the location channel, so jitter below the
    # Location Update Distance does not republish it.
    published_latitude = Tag("number", default=None)
    published_longitude = Tag("number", default=None)
    # Whether the last good fix was beyond the alert distance; the notification
    # fires on the change to True only.
    moved_away = Tag("boolean", default=None)
