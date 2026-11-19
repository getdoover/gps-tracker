from pathlib import Path

from pydoover import notifications as n


class GpsTrackerNotifications(n.Notifications):
    moved_away = n.Notification(
        "Moved away from its reference point",
        display_name="Moved away from reference point",
        description=(
            "A good GPS fix is further from the reference point than the alert "
            "distance. Only sent when Notify When Moved Away is on."
        ),
        severity=n.NotificationSeverity.Warn,
    )


def export():
    GpsTrackerNotifications.export(
        Path(__file__).parents[2] / "doover_config.json", "gps_tracker"
    )
