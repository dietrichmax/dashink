"""Renders Proxmox and weather stats as a PNG for an e-ink Kindle.

Endpoints:
  GET     /dash.png      the dashboard, or a photo when art is scheduled
  POST    /ingest/media  media pool usage, pushed by the collector on the storage host
  POST    /override      pin an image for a while, X-Dashink-Token
  DELETE  /override      drop the pinned image
  GET     /art.png       a photo now, ignoring the schedule
  GET     /state.json    raw source state, for debugging a render you cannot see
  GET     /healthz       liveness for the compose healthcheck
"""

import hmac
import logging
import os
import platform
from datetime import datetime

from flask import Flask, Response, jsonify, request

import render
from sources import (Expiring, immich_image, immich_source, kuma_source,
                     local_host_source, media_store, parse_media_payload,
                     pve_source, weather_source)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("dashink")


def _env(name, default=None, required=False):
    value = os.environ.get(name, default)
    if required and not value:
        raise RuntimeError(f"{name} is required (see .env.example)")
    return value


def _flag(name, default=False):
    return _env(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


# Everything below is optional. An unconfigured source is omitted from the panel
# rather than rendered as an error.
LANG = _env("LANG_CODE", "en")
NODE_NAME = _env("NODE_NAME", "") or _env("PVE_NODE", "") or platform.node()
WEATHER_LABEL = _env("WEATHER_LABEL", "")
VERIFY_SSL = _flag("PVE_VERIFY_SSL", False)

HOST_SOURCE = _env("HOST_SOURCE", "local").strip().lower()
PVE_HOST = _env("PVE_HOST", "")
PVE_TOKEN_ID = _env("PVE_TOKEN_ID", "")
PVE_TOKEN_SECRET = _env("PVE_TOKEN_SECRET", "")

if HOST_SOURCE == "proxmox" and PVE_HOST and PVE_TOKEN_ID and PVE_TOKEN_SECRET:
    if not VERIFY_SSL:
        # Proxmox serves a self-signed cert; without this every poll warns.
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    host = pve_source(
        host=PVE_HOST,
        port=_env("PVE_PORT", "8006"),
        node=_env("PVE_NODE", "pve"),
        token_id=PVE_TOKEN_ID,
        token_secret=PVE_TOKEN_SECRET,
        verify_ssl=VERIFY_SSL,
    )
else:
    if HOST_SOURCE == "proxmox":
        log.warning("HOST_SOURCE=proxmox but PVE_* is incomplete; using local /proc")
    host = local_host_source()

# --- weather: omitted without coordinates -----------------------------------
WEATHER_LAT = _env("WEATHER_LAT", "")
WEATHER_LON = _env("WEATHER_LON", "")
weather = (
    weather_source(WEATHER_LAT, WEATHER_LON, _env("WEATHER_TZ", "auto"))
    if WEATHER_LAT and WEATHER_LON
    else None
)

# --- media: omitted without an ingest token ---------------------------------
INGEST_TOKEN = _env("INGEST_TOKEN", "")
media = media_store() if INGEST_TOKEN else None

# --- monitors: omitted without a Kuma URL and key ---------------------------
KUMA_URL = _env("KUMA_URL", "")
KUMA_API_KEY = _env("KUMA_API_KEY", "")
kuma = kuma_source(KUMA_URL, KUMA_API_KEY) if KUMA_URL and KUMA_API_KEY else None

# --- art: a photo from Immich instead of the panel, inside a time window ----
IMMICH_URL = _env("IMMICH_URL", "")
IMMICH_API_KEY = _env("IMMICH_API_KEY", "")
ART_FROM = _env("ART_FROM", "").strip()
ART_UNTIL = _env("ART_UNTIL", "").strip()
try:
    ART_ALTERNATE = int(_env("ART_ALTERNATE_MINUTES", "0") or 0)
except ValueError:
    ART_ALTERNATE = 0

# A photo is re-picked once per art slot, so alternating gives a different one
# each time rather than the same picture every other refresh.
immich = (
    immich_source(IMMICH_URL, IMMICH_API_KEY, _env("IMMICH_ALBUM_ID", ""),
                  ttl=ART_ALTERNATE * 60 if ART_ALTERNATE else 3600)
    if IMMICH_URL and IMMICH_API_KEY
    else None
)


def _in_art_window(now):
    """HH:MM string comparison, wrapping past midnight for 22:00 -> 07:00."""
    if not (ART_FROM and ART_UNTIL):
        return False
    t = now.strftime("%H:%M")
    if ART_FROM <= ART_UNTIL:
        return ART_FROM <= t < ART_UNTIL
    return t >= ART_FROM or t < ART_UNTIL


def _show_art(now):
    """Window wins; outside it, alternate if asked to.

    Derived from the clock, not a request counter, so a browser opening the URL
    cannot shift the Kindle out of step.
    """
    if not immich:
        return False
    if _in_art_window(now):
        return True
    if ART_ALTERNATE:
        return ((now.hour * 60 + now.minute) // ART_ALTERNATE) % 2 == 1
    return False


def _art_png():
    """PNG bytes for a random photo, or None if anything goes wrong.

    Never raises: art is decoration and must not stop the dashboard rendering.
    """
    try:
        asset = immich.get()
        if not asset.get("ok"):
            return None
        return render.render_art(immich_image(IMMICH_URL, IMMICH_API_KEY, asset["id"]))
    except Exception as exc:
        log.warning("art unavailable, showing the panel instead: %s", exc)
        return None


if not any((weather, media, kuma)):
    log.warning("no weather, media or monitor source configured; "
                "the panel will show host stats only")

app = Flask(__name__)
# A panel is 600x800; nothing legitimate posted here is large. Without a cap,
# /override accepts an upload of any size straight into memory.
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024

# Pinned image, shown ahead of everything else until it expires. Reuses
# INGEST_TOKEN: no token means the endpoint is closed, same as /ingest/media.
override = Expiring()


def _state():
    return {
        "node": NODE_NAME,
        "lang": LANG,
        "label": WEATHER_LABEL,
        "now": datetime.now(),
        "host": host.get(),
        "media": media.get() if media else None,
        "weather": weather.get() if weather else None,
        "kuma": kuma.get() if kuma else None,
    }


@app.get("/dash.png")
def dash_png():
    png = override.get()
    if png is None:
        png = (_show_art(datetime.now()) and _art_png()) or render.render(_state())
    return Response(
        png,
        mimetype="image/png",
        # The Kindle fetches with curl on a timer; a cached copy would freeze it.
        headers={"Cache-Control": "no-store, must-revalidate"},
    )


@app.post("/ingest/media")
def ingest_media():
    # No token means no media source, so the endpoint is closed rather than
    # comparing against an empty secret that anything would match.
    if not media:
        return jsonify(error="media ingest not configured"), 503

    supplied = request.headers.get("X-Dashink-Token", "")
    if not hmac.compare_digest(supplied, INGEST_TOKEN):
        log.warning("rejected ingest from %s: bad token", request.remote_addr)
        return jsonify(error="unauthorized"), 401

    try:
        value = parse_media_payload(request.get_json(silent=True))
    except ValueError as exc:
        log.warning("rejected ingest from %s: %s", request.remote_addr, exc)
        return jsonify(error=str(exc)), 400

    media.put(value)
    log.info("media pool updated: %.2f TB of %.2f TB used",
             value["used"] / 1e12, value["total"] / 1e12)
    return jsonify(ok=True)


@app.post("/override")
def set_override():
    """Pin an image for a while. Any format Pillow reads; it goes through the
    same fit-and-dither path as the art."""
    if not INGEST_TOKEN:
        return jsonify(error="override is closed (no INGEST_TOKEN set)"), 503
    if not hmac.compare_digest(request.headers.get("X-Dashink-Token", ""), INGEST_TOKEN):
        return jsonify(error="unauthorized"), 401

    data = request.get_data()
    if not data:
        return jsonify(error="empty body: POST the image bytes"), 400
    try:
        png = render.render_art(data)
    except Exception as exc:
        return jsonify(error=f"could not read that image: {exc}"), 400

    try:
        minutes = max(1, min(int(request.args.get("minutes", 60)), 1440))
    except ValueError:
        return jsonify(error="minutes must be a number"), 400

    override.put(png, minutes * 60)
    log.info("panel overridden for %d minutes", minutes)
    return jsonify(ok=True, minutes=minutes)


@app.delete("/override")
def clear_override():
    if not INGEST_TOKEN:
        return jsonify(error="override is closed (no INGEST_TOKEN set)"), 503
    if not hmac.compare_digest(request.headers.get("X-Dashink-Token", ""), INGEST_TOKEN):
        return jsonify(error="unauthorized"), 401
    override.clear()
    log.info("panel override cleared")
    return jsonify(ok=True)


@app.get("/art.png")
def art_png():
    """Art on demand, ignoring the schedule, so the dithering can be judged now."""
    if not immich:
        return jsonify(error="immich not configured"), 503
    png = _art_png()
    if png is None:
        return jsonify(error="could not fetch a photo (see the logs)"), 502
    return Response(png, mimetype="image/png",
                    headers={"Cache-Control": "no-store, must-revalidate"})


@app.get("/state.json")
def state_json():
    state = _state()
    state["now"] = state["now"].isoformat()
    return jsonify(state)


@app.get("/healthz")
def healthz():
    return jsonify(ok=True)


if __name__ == "__main__":
    # Development only, and loopback only: this has no token on /dash.png and
    # the container serves the real thing through gunicorn (see the Dockerfile).
    app.run(host="127.0.0.1", port=8099)
