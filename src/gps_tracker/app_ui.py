from pydoover import ui


class GpsTrackerUI(ui.UI, hidden=True):
    """No panel on the device page.

    The app's output is the device's position on the device page and the
    organisation map (the location channel), plus its tags. The UI is declared
    empty and hidden so the published schema replaces any earlier panel.
    """


def export():
    from pathlib import Path

    GpsTrackerUI(None, None, None).export(
        Path(__file__).parents[2] / "doover_config.json",
        "gps_tracker",
    )
