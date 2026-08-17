# dashink

Homelab status and weather rendered to a 600x800 greyscale PNG for a jailbroken Kindle used as a wall dashboard.

![dashboard](docs/dash.png)

![the panel running on a Kindle](docs/device.jpg)

Built for a **Kindle 7th Generation (KT2, 2014)** on firmware `5.12.2.2`: 600x800, 167 ppi, 16 grey levels, no front light. Any device that can fetch a URL and draw a PNG will work; the size is set by `server/render.py`.

The service does one thing: `GET /dash.png` renders the current panel from whatever the sources last returned. There is no scheduler and nothing persisted. The Kindle fetches that URL on a loop and draws it to the framebuffer. E-ink holds the last image with no power, so a device that dies mid-loop leaves a readable screen.

![how the pieces fit together](docs/architecture.svg)

## Quickstart

```bash
git clone https://github.com/dietrichmax/dashink
cd dashink
cp .env.example .env
```

Set `WEATHER_LAT` and `WEATHER_LON` in `.env`, in decimal degrees. That is the only edit needed. Every source is optional and each one is omitted from the panel when it is not configured, so two coordinates already give you a usable screen.

```bash
docker compose up -d
curl -o dash.png http://localhost:8099/dash.png
```

Open `dash.png` and you should have weather, a host tile and a footer. Add `KUMA_*`, `IMMICH_*` and the storage collector as you want them; nothing else has to change when you do.

Then point whatever is going to display it at `http://<host>:8099/dash.png`, using the machine's LAN address rather than `localhost`. Any always-on browser in fullscreen will do. [docs/kindle.md](docs/kindle.md) is the e-ink route.

## Configuration

All of it lives in `.env`. Nothing is required.

| Variable | |
|---|---|
| `LANG_CODE` | `en` or `de`. A new language is one file in [`server/lang/`](server/lang/) |
| `NODE_NAME` | shown top-left. Falls back to the container hostname |
| `HOST_SOURCE` | `local` reads `/proc`; `proxmox` uses the node API |
| `WEATHER_LAT` / `WEATHER_LON` | empty omits the whole weather block |
| `INGEST_TOKEN` | empty closes `/ingest/media` and `/override`, and drops the storage tile |
| `KUMA_URL` / `KUMA_API_KEY` | both empty drops the monitors tile |
| `IMMICH_URL` / `IMMICH_API_KEY` | both empty drops the art feature |
| `IMMICH_ALBUM_ID` | empty picks from the whole library |
| `ART_FROM` / `ART_UNTIL` | photos for a stretch of the day; a later `FROM` wraps past midnight |
| `ART_ALTERNATE_MINUTES` | outside that window, alternate panel and photo every N minutes. `0` disables |

`.env.example` carries the longer notes for each one.

The top row has two slots, filled in priority order: **monitors**, **storage**, then **host**. Host stats only appear when one of the other two is absent.

![the monitor and storage tiles](docs/tiles.jpg)

Weather fills the lower two thirds. The upper part is today in full, then three day columns with low and high temperature, the condition, and rain probability where it is at least 20%.

![the weather section](docs/weather.jpg)

## Failure behaviour

A source that stops responding keeps its last value and lets the age grow. Past 3x its TTL the tile is marked `!`, the footer lists it under `stale:`, and a source that never succeeded shows `n/a` instead of a number.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/dash.png` | the dashboard, 600x800 greyscale PNG, or a photo when art is scheduled |
| `GET` | `/art.png` | a photo now, ignoring the schedule, to judge the dithering |
| `POST` | `/ingest/media` | collector push, `X-Dashink-Token` header |
| `POST` | `/override` | pin an image (any format Pillow reads) for `?minutes=`, 1–1440, default 60. `X-Dashink-Token` |
| `DELETE` | `/override` | drop the pinned image. `X-Dashink-Token` |
| `GET` | `/state.json` | raw source state, for debugging |
| `GET` | `/healthz` | compose healthcheck |

Pinning an image, for a note on the wall or a photo for the evening:

```bash
TOKEN=<INGEST_TOKEN>
curl -f -H "X-Dashink-Token: $TOKEN" --data-binary @poster.png \
  "http://<host>:8099/override?minutes=120"
curl -f -X DELETE -H "X-Dashink-Token: $TOKEN" http://<host>:8099/override
```

## Optional sources

### Storage tile

The tile is filled by POSTing to `/ingest/media`, so anything that can produce three numbers can drive it. [`collect/dashink-collect.sh`](collect/dashink-collect.sh) is the collector this project uses: it reports pool fill from `df` and, if there is one, disk health from the newest `/var/log/snapraid-smart-*.log`.

Install it on the machine that can see the pool, with its config in `/etc/dashink.env`:

```bash
printf 'DASHINK_URL=http://<host>:8099/ingest/media\nDASHINK_TOKEN=<INGEST_TOKEN>\n' \
  > /etc/dashink.env
chmod 600 /etc/dashink.env
/path/to/dashink-collect.sh     # verify before trusting cron
```

**Run it every 15 minutes, which pairs with the 30-minute TTL on the media store:** two pushes per window, so one missed run does not flip the tile to `stale`. An interval equal to the TTL would show stale data on nothing worse than cron drift.

The SMART half is fail-soft. A missing or unparseable log omits the field, the panel keeps showing uptime, and it can never take the pool figures down with it.

Frequency costs nothing here: `df` reads the cached in-memory superblock, and the SMART figures come from a log on the system disk. Neither wakes a parked drive. Keep it that way: no `du`, no `find`, no `smartctl`, nothing that walks the tree or touches the array, or the disks never spin down under hd-idle.

### Proxmox host stats

Only worth setting `HOST_SOURCE=proxmox` if you run Proxmox, and even then it supplies little the panel shows. Read-only token, on the host:

```bash
pveum user add dashink@pve
pveum aclmod / -user dashink@pve -role PVEAuditor
pveum user token add dashink@pve dash --privsep 0
```

The secret is shown once. To rotate: `token remove` then `token add` again. An incomplete `PVE_*` block falls back to `local` rather than failing to boot.

### Photos from Immich

With `IMMICH_URL` and `IMMICH_API_KEY` set, `/dash.png` serves a photo instead of the panel on a schedule. `ART_FROM` / `ART_UNTIL` give it a window of the day, `ART_ALTERNATE_MINUTES` swaps between the panel and a photo every N minutes outside that window, and `IMMICH_ALBUM_ID` narrows the source to one album rather than the whole library.

Photos are cover-fitted to the panel and dithered rather than posterised, because hard quantisation puts contour lines across every sky. `GET /art.png` returns one immediately and ignores the schedule, which is the quickest way to judge how a given album comes out.

![a photo on the panel](docs/art.jpg)

## The Kindle

Jailbreaking the KT2, KUAL, SSH over USBNetwork, and the three scripts in [`kindle/`](kindle/) are their own document: **[docs/kindle.md](docs/kindle.md)**.

## Licence

MIT. Weather data from [Open-Meteo](https://open-meteo.com/).
