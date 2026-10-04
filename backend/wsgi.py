"""WSGI entry point for gunicorn (backend/gunicorn.conf.py): `gunicorn -c gunicorn.conf.py wsgi:app`."""

import os

# gunicorn.conf.py sets this too; keeps threads out of the pre-fork master when preloading.
os.environ.setdefault("SR_DEFER_BACKGROUND_JOBS", "1")

from config import Config  # noqa: E402
from main import create_app, start_background_jobs  # noqa: E402,F401

app = create_app(Config)
