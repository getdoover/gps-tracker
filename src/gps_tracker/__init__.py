from pydoover.processor import run_app

from .application import GpsTrackerApplication


def handler(event, context):
    """Lambda handler entry point."""
    return run_app(
        GpsTrackerApplication(),
        event,
        context,
    )
