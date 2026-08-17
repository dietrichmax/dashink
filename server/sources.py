"""Data sources for the dashboard.

Each source keeps its last good value. A failed refresh does not blank the tile:
it keeps the old value and lets the age grow, so render.py can mark the tile
stale.
"""

import logging
import os
import re
import threading
import time

import requests

log = logging.getLogger(__name__)

OPEN_METEO = "https://api.open-meteo.com/v1/forecast"

# A value older than STALE_FACTOR x its TTL means refreshes are failing.
STALE_FACTOR = 3


class Cached:
    """Last-good-value cache with a TTL, refreshed lazily on read."""

    def __init__(self, ttl, fetch):
        self.ttl = ttl
        self._fetch = fetch
        self._value = None
        self._at = 0.0
        self._lock = threading.Lock()

    def get(self):
        with self._lock:
            if self._value is None or (time.time() - self._at) >= self.ttl:
                try:
                    self._value = self._fetch()
                    self._at = time.time()
                except Exception as exc:  # network, auth, malformed payload
                    log.warning("refresh failed: %s", exc)
            return _wrap(self._value, self._at, self.ttl)


class PushStore:
    """Holds the newest payload POSTed by the collector on the storage host.

    The pool is only visible from that machine, which need not be the one
    running dashink, so it pushes rather than this service pulling.
    """

    def __init__(self, ttl):
        self.ttl = ttl
        self._value = None
        self._at = 0.0
        self._lock = threading.Lock()

    def put(self, value):
        with self._lock:
            self._value = value
            self._at = time.time()

    def get(self):
        with self._lock:
            return _wrap(self._value, self._at, self.ttl)


class Expiring:
    """A value that clears itself at a deadline.

    Used for the panel override, so "temporarily" is enforced rather than
    remembered.
    """

    def __init__(self):
        self._value = None
        self._until = 0.0
        self._lock = threading.Lock()

    def put(self, value, seconds):
        with self._lock:
            self._value = value
            self._until = time.time() + seconds

    def clear(self):
        with self._lock:
            self._value = None
            self._until = 0.0

    def get(self):
        with self._lock:
            if self._value is not None and time.time() >= self._until:
                self._value = None
            return self._value


def _wrap(value, at, ttl):
    if value is None:
        return {"ok": False, "stale": True, "age": None}
    age = time.time() - at
    return {"ok": True, "stale": age > ttl * STALE_FACTOR, "age": age, **value}


def pve_source(host, port, node, token_id, token_secret, verify_ssl, ttl=300):
    """Node-level CPU and memory from the Proxmox API.

    /nodes/<node>/status only: that endpoint never touches the SnapRAID disks,
    so polling it cannot interfere with hd-idle spindown.
    """
    url = f"https://{host}:{port}/api2/json/nodes/{node}/status"
    headers = {"Authorization": f"PVEAPIToken={token_id}={token_secret}"}

    def fetch():
        r = requests.get(url, headers=headers, verify=verify_ssl, timeout=8)
        r.raise_for_status()
        data = r.json()["data"]
        mem = data.get("memory", {})
        return {
            "cpu": float(data.get("cpu", 0.0)),
            "cpus": int(data.get("cpuinfo", {}).get("cpus", 0)),
            "mem_used": int(mem.get("used", 0)),
            "mem_total": int(mem.get("total", 0)),
            "uptime": int(data.get("uptime", 0)),
        }

    return Cached(ttl, fetch)


def local_host_source(ttl=60):
    """CPU load, memory and uptime from /proc. Same shape as pve_source.

    Load average rather than a CPU percentage: an instantaneous sample can land
    between two bursts and read near zero on a busy machine. In a container
    /proc is the host's, which is what the panel should report on.
    """

    def fetch():
        with open("/proc/loadavg") as f:
            load1 = float(f.read().split()[0])
        with open("/proc/uptime") as f:
            uptime = float(f.read().split()[0])

        mem = {}
        with open("/proc/meminfo") as f:
            for line in f:
                key, _, rest = line.partition(":")
                if key in ("MemTotal", "MemAvailable"):
                    mem[key] = int(rest.split()[0]) * 1024  # kB -> bytes
                if len(mem) == 2:
                    break

        cpus = os.cpu_count() or 1
        total = mem.get("MemTotal", 0)
        avail = mem.get("MemAvailable", 0)
        return {
            "cpu": min(load1 / cpus, 1.0),
            "cpus": cpus,
            "load": load1,
            "mem_used": total - avail,
            "mem_total": total,
            "uptime": int(uptime),
        }

    return Cached(ttl, fetch)


def weather_source(lat, lon, tz, ttl=1800):
    """Current conditions plus the next three days from Open-Meteo (no API key)."""

    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,weather_code",
        "daily": ("weather_code,temperature_2m_max,temperature_2m_min,"
                  "sunrise,sunset,precipitation_probability_max"),
        "timezone": tz,
        "forecast_days": 4,  # index 0 is today; we show 1..3
    }

    def fetch():
        r = requests.get(OPEN_METEO, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        current, daily = data["current"], data["daily"]

        # Open-Meteo intermittently answers 200 with "temperature_2m": null.
        # Raising keeps the last good value and lets the tile go stale;
        # returning it renders round(None) and 500s the whole panel.
        if current.get("temperature_2m") is None:
            raise ValueError("no current temperature in Open-Meteo response")

        days = [
            {
                "date": daily["time"][i],
                "code": daily["weather_code"][i],
                "tmax": daily["temperature_2m_max"][i],
                "tmin": daily["temperature_2m_min"][i],
                # None rather than 0 when the API omits it, so the panel can
                # tell "no chance of rain" from "no data".
                "pop": (daily.get("precipitation_probability_max") or [None] * 4)[i],
            }
            for i in range(1, min(4, len(daily["time"])))
        ]
        return {
            "temp": current["temperature_2m"],
            "code": current["weather_code"],
            # Today's range, from index 0, the one days[] skips.
            "tmin": daily["temperature_2m_min"][0],
            "tmax": daily["temperature_2m_max"][0],
            # "2026-08-15T06:14" -> "06:14". Sliced, not parsed: the API already
            # returns these in the requested timezone, and parsing would add a
            # tzdata dependency the image does not otherwise need.
            "sunrise": daily["sunrise"][0][11:16],
            "sunset": daily["sunset"][0][11:16],
            "days": days,
        }

    return Cached(ttl, fetch)


_KUMA_NAME = re.compile(r'monitor_name="([^"]*)"')


def kuma_source(base_url, api_key, ttl=120):
    """Monitor states from Uptime Kuma's Prometheus endpoint.

    /metrics rather than Kuma's socket.io API: one GET, and it covers every
    monitor rather than only those added to a status page. Auth is HTTP Basic
    with an empty username and the API key as the password.
    """
    url = f"{base_url.rstrip('/')}/metrics"

    def fetch():
        r = requests.get(url, auth=("", api_key), timeout=10)
        r.raise_for_status()

        total, down = 0, []
        for line in r.text.splitlines():
            if not line.startswith("monitor_status{"):
                continue
            # 0 down, 1 up, 2 pending, 3 maintenance. Only 0 is a problem.
            # Counted after the parse, so Kuma's "Nan" (a monitor with no
            # heartbeat yet) is left out rather than counted as up.
            try:
                status = int(float(line.rsplit(" ", 1)[-1]))
            except ValueError:
                continue
            total += 1
            if status == 0:
                name = _KUMA_NAME.search(line)
                down.append(name.group(1) if name else "?")

        # A 200 with no monitors means the wrong response, not an empty Kuma:
        # a proxy login page, or /metrics turned off. Returning it would render
        # "0/0 all up", a false all-clear.
        if not total:
            raise ValueError("no monitor_status lines in /metrics")

        return {"total": total, "down": down}

    return Cached(ttl, fetch)


def immich_source(base_url, api_key, album_id="", ttl=3600):
    """One random photo from Immich, re-picked once per TTL.

    Hourly rather than every refresh: the Kindle only does a full e-ink clear
    every twelfth cycle, and changing faster than that leaves the previous
    photo ghosting underneath.
    """
    url = f"{base_url.rstrip('/')}/api/search/random"
    headers = {"x-api-key": api_key, "Content-Type": "application/json"}
    body = {"size": 1, "type": "IMAGE"}
    if album_id:
        body["albumIds"] = [album_id]

    def fetch():
        r = requests.post(url, headers=headers, json=body, timeout=10)
        r.raise_for_status()
        assets = r.json()
        if not assets:
            raise ValueError("no assets returned (check the album filter)")
        asset = assets[0]
        return {"id": asset["id"], "name": asset.get("originalFileName", "")}

    return Cached(ttl, fetch)


def immich_image(base_url, api_key, asset_id):
    """Bytes of a rendered preview, not the original: no point decoding a 40
    megapixel file to fill a 600x800 panel."""
    r = requests.get(
        f"{base_url.rstrip('/')}/api/assets/{asset_id}/thumbnail",
        params={"size": "preview"},
        headers={"x-api-key": api_key},
        timeout=15,
    )
    r.raise_for_status()
    return r.content


def media_store(ttl=1800):
    """Media pool usage, pushed by collect/dashink-collect.sh on the storage host."""
    return PushStore(ttl)


def parse_media_payload(payload):
    """Validate a collector POST. Raises ValueError on anything unusable."""
    if not isinstance(payload, dict):
        raise ValueError("payload is not an object")
    try:
        total = int(payload["total"])
        used = int(payload["used"])
        avail = int(payload["avail"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"missing or non-numeric total/used/avail: {exc}") from exc
    if total <= 0:
        raise ValueError("total must be positive")

    result = {"total": total, "used": used, "avail": avail}
    # SMART is optional: passed through unvalidated so a malformed block cannot
    # reject an otherwise valid pool reading. render.py reads it defensively.
    smart = payload.get("smart")
    if isinstance(smart, dict):
        result["smart"] = smart
    return result
