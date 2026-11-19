import logging
import time

from pydoover.models import MessageCreateEvent
from pydoover.processor import Application

from . import geo
from .app_config import GpsTrackerConfig
from .app_notifications import GpsTrackerNotifications
from .app_tags import GpsTrackerTags
from .app_ui import GpsTrackerUI, has_reference_point

log = logging.getLogger(__name__)

# The channel the Doover site reads a device's position from: its aggregate is
# the current position on the device page and organisation map, its messages are
# the location history (track). Keys are "lat" / "long", decimal degrees.
LOCATION_CHANNEL = "location"

# Optional readings, by config field and the name they go by in this app.
_OPTIONAL_PATHS = {
    "altitude": "altitude_path",
    "satellites": "satellites_path",
    "hdop": "hdop_path",
    "fix_status": "fix_status_path",
    "gps_time": "gps_time_path",
}


class GpsTrackerApplication(Application):
    config: GpsTrackerConfig
    tags: GpsTrackerTags
    ui: GpsTrackerUI
    notifications: GpsTrackerNotifications

    config_cls = GpsTrackerConfig
    tags_cls = GpsTrackerTags
    ui_cls = GpsTrackerUI
    notifications_cls = GpsTrackerNotifications

    async def setup(self):
        self._channel = None
        self._lat_path = self._lon_path = None
        self._optional: dict[str, tuple[str, list[str]]] = {}
        try:
            lat = geo.parse_path(self.config.latitude_path.value)
            lon = geo.parse_path(self.config.longitude_path.value)
        except (TypeError, ValueError) as e:
            log.error("GPS Tracker is not configured correctly: %s", e)
            return
        if lat is None or lon is None:
            log.error("GPS Tracker needs both a latitude and a longitude message path.")
            return
        if lat[0] != lon[0]:
            log.error(
                "Latitude ($%s) and longitude ($%s) must be on the same channel.",
                lat[0],
                lon[0],
            )
            return
        self._channel, self._lat_path, self._lon_path = lat[0], lat[1], lon[1]

        for key, field in _OPTIONAL_PATHS.items():
            try:
                parsed = geo.parse_path(getattr(self.config, field).value)
            except (TypeError, ValueError) as e:
                log.warning("Ignoring %s: %s", field, e)
                continue
            if parsed is not None:
                self._optional[key] = parsed

    async def on_message_create(self, event: MessageCreateEvent):
        if self._channel is None or event.channel.name != self._channel:
            return
        await self.handle_reading(event.channel.name, event.message.data or {})

    # -- the reading ----------------------------------------------------------

    def _optional_value(self, key: str, channel: str, data: dict):
        """An optional reading from this message, if its path is on this channel."""
        parsed = self._optional.get(key)
        if parsed is None or parsed[0] != channel:
            return None
        return geo.extract(data, parsed[1])

    async def handle_reading(self, channel: str, data: dict):
        lat = geo.to_float(geo.extract(data, self._lat_path))
        lon = geo.to_float(geo.extract(data, self._lon_path))
        altitude = geo.to_float(self._optional_value("altitude", channel, data))
        satellites = geo.to_float(self._optional_value("satellites", channel, data))
        hdop = geo.to_float(self._optional_value("hdop", channel, data))
        fix_status = geo.to_fix_status(
            self._optional_value("fix_status", channel, data)
        )
        gps_time = geo.to_epoch_ms(self._optional_value("gps_time", channel, data))

        has_position = lat is not None or lon is not None
        has_quality = (
            satellites is not None or hdop is not None or fix_status is not None
        )
        if not has_position and not has_quality:
            # A message on the channel that carries nothing GPS: not a reading.
            return

        # Quality readings are published as they are, good fix or not: they are
        # what tells an operator why there is no position.
        if satellites is not None:
            await self.tags.satellites.set(satellites)
        if hdop is not None:
            await self.tags.hdop.set(hdop)

        reason = geo.fix_rejection(
            fix_status=fix_status,
            satellites=satellites,
            hdop=hdop,
            min_satellites=self.config.min_satellites.value,
            max_hdop=self.config.max_hdop.value,
        )
        if reason is None and not geo.valid_coordinates(lat, lon):
            reason = "no valid position" if has_position else "no position"
        if reason is not None:
            log.info("Ignoring GPS reading on %s: %s", channel, reason)
            await self.tags.fix_ok.set(False)
            await self.tags.fix_quality.set(f"Ignored: {reason}")
            return

        await self.tags.fix_ok.set(True)
        await self.tags.fix_quality.set(self._quality_text(satellites, hdop))
        await self.tags.latitude.set(lat)
        await self.tags.longitude.set(lon)
        if altitude is not None:
            await self.tags.altitude.set(altitude)
        await self.tags.last_fix_ts.set(gps_time or int(time.time() * 1000))

        await self._publish_location(lat, lon, altitude, satellites, hdop)
        await self._update_reference(lat, lon)

    @staticmethod
    def _quality_text(satellites, hdop) -> str:
        parts = []
        if satellites is not None:
            parts.append(f"{satellites:g} satellites")
        if hdop is not None:
            parts.append(f"HDOP {hdop:g}")
        return "Good" + (f" ({', '.join(parts)})" if parts else "")

    # -- map location ---------------------------------------------------------

    async def _publish_location(self, lat, lon, altitude, satellites, hdop):
        last_lat = self.tags.published_latitude.get()
        last_lon = self.tags.published_longitude.get()
        min_move = self.config.location_min_move_m.value or 0.0
        if (
            last_lat is not None
            and last_lon is not None
            and min_move > 0
            and geo.distance_m(last_lat, last_lon, lat, lon) < min_move
        ):
            return

        location = {"lat": lat, "long": lon}
        if altitude is not None:
            location["alt"] = altitude
        if satellites is not None:
            location["satellites"] = satellites
        if hdop is not None:
            location["hdop"] = hdop

        await self.api.update_channel_aggregate(
            LOCATION_CHANNEL, location, replace_data=True
        )
        await self.api.create_message(LOCATION_CHANNEL, location)
        await self.tags.published_latitude.set(lat)
        await self.tags.published_longitude.set(lon)

    # -- reference point --------------------------------------------------------

    async def _update_reference(self, lat, lon):
        if not has_reference_point(self.config):
            # Cleared rather than left stale if the reference point is removed.
            if self.tags.bearing_deg.get() is not None:
                await self.tags.bearing_deg.set(None)
            if self.tags.distance_m.get() is not None:
                await self.tags.distance_m.set(None)
            return

        ref_lat = self.config.reference_latitude.value
        ref_lon = self.config.reference_longitude.value
        offset = self.config.bearing_offset_deg.value or 0.0
        distance = geo.distance_m(ref_lat, ref_lon, lat, lon)
        await self.tags.bearing_deg.set(
            round(geo.bearing_deg(ref_lat, ref_lon, lat, lon, offset), 2)
        )
        await self.tags.distance_m.set(round(distance, 2))
        await self._check_moved_away(distance)

    async def _check_moved_away(self, distance: float):
        if not self.config.notify_on_move.value:
            return
        limit = self.config.move_alert_distance_m.value
        if limit is None or limit <= 0:
            return
        away = distance > limit
        was_away = bool(self.tags.moved_away.get())
        if away == was_away:
            return
        await self.tags.moved_away.set(away)
        if away:
            await self.notifications.moved_away.send(
                f"Moved {distance:,.0f} m from its reference point "
                f"(alert distance {limit:,.0f} m)."
            )
