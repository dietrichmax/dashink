"""Shared fixtures.

DejaVu lives somewhere different on every distro -- truetype/dejavu on Debian,
dejavu on Alpine, dejavu-sans-fonts on Fedora -- so the font directory is
probed and exported before render.py reads it at import time. Without this the
render tests pass or fail depending on which machine runs them.
"""

import glob
import os

_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu",      # Debian, Ubuntu
    "/usr/share/fonts/dejavu",               # Alpine
    "/usr/share/fonts/dejavu-sans-fonts",    # Fedora
)


def _font_dir():
    if os.environ.get("DASHINK_FONT_DIR"):
        return os.environ["DASHINK_FONT_DIR"]
    for d in _CANDIDATES:
        if os.path.isfile(os.path.join(d, "DejaVuSans.ttf")):
            return d
    hits = glob.glob("/usr/share/fonts/**/DejaVuSans.ttf", recursive=True)
    return os.path.dirname(hits[0]) if hits else ""


FONT_DIR = _font_dir()
if FONT_DIR:
    os.environ["DASHINK_FONT_DIR"] = FONT_DIR

import pytest  # noqa: E402  (must follow the env setup above)

import app as dashink_app  # noqa: E402
import sources  # noqa: E402

TOKEN = "test-token"

needs_font = pytest.mark.skipif(
    not FONT_DIR, reason="DejaVu not installed; set DASHINK_FONT_DIR"
)


@pytest.fixture
def client():
    dashink_app.app.config.update(TESTING=True)
    return dashink_app.app.test_client()


@pytest.fixture
def app_module():
    return dashink_app


@pytest.fixture
def ingest(monkeypatch):
    """A configured media ingest, as setting INGEST_TOKEN in .env would give."""
    store = sources.media_store()
    monkeypatch.setattr(dashink_app, "INGEST_TOKEN", TOKEN)
    monkeypatch.setattr(dashink_app, "media", store)
    return store
