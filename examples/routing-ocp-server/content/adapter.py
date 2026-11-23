"""Explicit factory selected by the installing author, not remote metadata."""
from .engine import LibraryConnector
from .checker import RoutingChecker
from .input_files import converters


def create_bundle(settings):
    if settings.get("api_endpoint"):
        from .http_api import HTTPConnector
        connector = HTTPConnector.from_settings(settings)
    else:
        connector = LibraryConnector()
    return {"connector": connector, "checker": RoutingChecker(), "converters": converters()}
