"""ASGI entrypoint for the nutrition tracker API."""

from nutrition_tracker.api.app import create_app
from nutrition_tracker.containers import build_container

app = create_app(build_container())
