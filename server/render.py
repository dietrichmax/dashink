"""Renders the dashboard to a 600x800 greyscale PNG for a Kindle KT2 e-ink panel.

Design constraints that drive everything here:
  * 600x800 at 167 ppi, 16 grey levels, and NO front light. Contrast has to
    carry the layout, so tiles are separated by rules rather than by fill, and
    anything that matters is pure black on white.
  * Values are large enough to read across a room; labels are not.
  * A tile whose source stopped updating gets marked, never silently frozen.
"""

import io
import os
from datetime import date, datetime

from PIL import Image, ImageDraw, ImageFont

import i18n

W, H = 600, 800
MARGIN = 24
BLACK, GREY, LIGHT, WHITE = 0, 110, 190, 255

# Where the container's fonts-dejavu-core lands. Override it for local
# development on anything that is not Debian.
FONT_DIR = os.environ.get("DASHINK_FONT_DIR", "/usr/share/fonts/truetype/dejavu")
_FONTS = {}

# Horizontal rules, top to bottom: under the header, under the tiles, above the
# footer.
Y_HEAD, Y_TILES, Y_WEATHER = 64, 300, 726

def _font(name, size):
    key = (name, size)
    if key not in _FONTS:
        _FONTS[key] = ImageFont.truetype(f"{FONT_DIR}/{name}", size)
    return _FONTS[key]


def bold(size):
    return _font("DejaVuSans-Bold.ttf", size)


def regular(size):
    return _font("DejaVuSans.ttf", size)


def _dec(value, sep, digits=1):
    """Decimal formatting with the language's separator."""
    return f"{value:.{digits}f}".replace(".", sep)


def _rule(d, y, fill=BLACK, width=2, inset=0):
    d.line([MARGIN + inset, y, W - MARGIN - inset, y], fill=fill, width=width)


def _bar(d, x, y, w, h, frac):
    """Outlined bar with a solid fill. frac None renders an empty bar."""
    d.rectangle([x, y, x + w, y + h], outline=BLACK, width=2)
    if frac is None:
        return
    inner = int((w - 4) * max(0.0, min(1.0, frac)))
    if inner > 0:
        d.rectangle([x + 2, y + 2, x + 2 + inner, y + h - 2], fill=BLACK)


def _pct(frac, na):
    # "n/a" rather than a dash: at 68px a dash is just a floating line and reads
    # as a rendering glitch rather than as missing data.
    return na if frac is None else f"{round(frac * 100)}%"


def _uptime(seconds):
    days, rem = divmod(int(seconds), 86400)
    hours = rem // 3600
    return f"{days}d {hours}h" if days else f"{hours}h"


def _tile_label(d, cx, text, stale):
    """Shared header for the two top tiles, so they line up exactly."""
    d.text((cx, 86), text + (" !" if stale else ""), font=bold(17), fill=GREY, anchor="ma")


def _sun_line(d, y, wx):
    """Sunrise and sunset on one line, left, sharing a baseline with today's range.

    Left, not centred: right-aligned conditions grow leftwards into a centre
    column. U+2600 and U+263E from DejaVu, not emoji — PIL cannot draw a colour
    emoji onto an "L" canvas.
    """
    rise, set_ = wx.get("sunrise"), wx.get("sunset")
    if not (rise and set_):
        return
    d.text((MARGIN, y), f"☀ {rise}    ☾ {set_}",
           font=regular(22), fill=GREY, anchor="la")


def _media_tile(d, cx, media, t):
    """Storage fill. Shares the top row with whatever else is configured."""
    s = t["s"]
    _tile_label(d, cx, s["media"], media.get("stale", False))

    ok = media.get("ok")
    used, avail = media.get("used"), media.get("avail", 0)
    # used/(used+avail), not used/total. That is how df computes Use%, and the
    # ext4 reserved blocks on each branch make the two differ by a point or two.
    frac = (used / (used + avail)) if ok and (used + avail) else None

    d.text((cx, 116), _pct(frac, s["na"]), font=bold(68), fill=BLACK, anchor="ma")
    _bar(d, cx - 100, 212, 200, 18, frac)

    if not ok:
        d.text((cx, 244), s["no_host_data"], font=regular(20), fill=GREY, anchor="ma")
        return
    tb = 1_000_000_000_000
    d.text((cx, 244), f"{_dec(avail / tb, s['decimal'])} TB {s['free']}",
           font=regular(20), fill=BLACK if (frac or 0) >= 0.9 else GREY, anchor="ma")


def _kuma_tile(d, cx, kuma, t):
    """Uptime Kuma monitor states.

    Quiet until something breaks: grey when everything is up, black and naming
    names when it is not.
    """
    s = t["s"]
    _tile_label(d, cx, s["services"], kuma.get("stale", False))

    if not kuma.get("ok"):
        d.text((cx, 150), s["na"], font=bold(48), fill=GREY, anchor="ma")
        d.text((cx, 244), s["no_connection"], font=regular(20), fill=GREY, anchor="ma")
        return

    down = kuma.get("down") or []
    total = kuma.get("total") or 0
    d.text((cx, 116), f"{total - len(down)}/{total}", font=bold(68),
           fill=BLACK, anchor="ma")

    if not down:
        d.text((cx, 244), s["all_up"], font=regular(20), fill=GREY, anchor="ma")
        return

    names = ", ".join(down)
    if len(names) > 26:
        names = s["n_down"].format(n=len(down))
    d.text((cx, 244), names, font=bold(20), fill=BLACK, anchor="ma")


def _host_tile(d, cx, host, t):
    """CPU load and memory for the machine dashink runs on.

    Only drawn when a slot is free, so an install with neither monitors nor
    storage still shows something real. On a Proxmox host these numbers barely
    move, so the other tiles displace this one. See the README.
    """
    s = t["s"]
    _tile_label(d, cx, s["host"], host.get("stale", False))

    if not host.get("ok"):
        d.text((cx, 150), s["na"], font=bold(48), fill=GREY, anchor="ma")
        return

    frac = host.get("cpu")
    d.text((cx, 116), _pct(frac, s["na"]), font=bold(68), fill=BLACK, anchor="ma")
    _bar(d, cx - 100, 212, 200, 18, frac)

    gb = 2 ** 30
    used, total = host.get("mem_used") or 0, host.get("mem_total") or 0
    sub = (f"{_dec(used / gb, s['decimal'])} / {_dec(total / gb, s['decimal'])} GB"
           if total else f"{host.get('cpus') or 0} {s['cores']}")
    d.text((cx, 244), sub, font=regular(20), fill=BLACK, anchor="ma")


def render_art(data):
    """A photograph, fitted to the panel and dithered for e-ink.

    Dithered, not posterised like the dashboard: hard quantisation puts contour
    lines across every sky and face. Cover-fitted, not letterboxed: white bars
    on a white panel read as a failed render.
    """
    img = Image.open(io.BytesIO(data)).convert("L")

    scale = max(W / img.width, H / img.height)
    img = img.resize((round(img.width * scale), round(img.height * scale)),
                     Image.LANCZOS)
    left, top = (img.width - W) // 2, (img.height - H) // 2
    img = img.crop((left, top, left + W, top + H))

    img = img.quantize(colors=16, dither=Image.Dither.FLOYDSTEINBERG).convert("L")

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render(state):
    """state -> PNG bytes. Every source except `host` may be None; the panel
    composes from whatever is configured rather than rendering placeholders."""
    t = i18n.catalogue(state.get("lang", i18n.DEFAULT))
    s = t["s"]

    img = Image.new("L", (W, H), WHITE)
    d = ImageDraw.Draw(img)

    now = state.get("now") or datetime.now()
    host = state.get("host") or {}
    media = state.get("media")
    wx = state.get("weather")
    kuma = state.get("kuma")

    # --- header ----------------------------------------------------------
    d.text((MARGIN, 32), state.get("node", ""), font=bold(24), fill=BLACK, anchor="lm")
    # Day and date, no clock. The footer's "updated HH:MM" is how you tell a
    # live panel from a frozen one, so a second clock up here was duplicate
    # ink. The weekday is the part worth reading across a room.
    d.text((W - MARGIN, 32),
           f"{t['weekdays_long'][now.weekday()]}, {now.strftime(s['date'])}",
           font=regular(22), fill=BLACK, anchor="rm")
    _rule(d, Y_HEAD)

    # --- top row ---------------------------------------------------------
    # Two slots, filled in priority order. Host stats only get one when
    # monitors or storage is absent.
    tiles = []
    if kuma:
        tiles.append(lambda cx: _kuma_tile(d, cx, kuma, t))
    if media:
        tiles.append(lambda cx: _media_tile(d, cx, media, t))
    if len(tiles) < 2:
        tiles.append(lambda cx: _host_tile(d, cx, host, t))

    for cx, draw in zip((150, 450) if len(tiles) > 1 else (W // 2,), tiles):
        draw(cx)
    if len(tiles) > 1:
        d.line([W // 2, 88, W // 2, 276], fill=LIGHT, width=2)
    _rule(d, Y_TILES)

    # --- weather ---------------------------------------------------------
    # Omitted entirely without coordinates rather than drawn as an empty
    # section: an empty weather box reads as a broken render.
    if wx is not None:
        label = state.get("label", "")
        head = s["weather"] + (f" · {label}" if label else "") + (" !" if wx.get("stale") else "")
        d.text((MARGIN, 336), head, font=bold(17), fill=GREY, anchor="la")

        if wx.get("ok"):
            full, _ = t["wmo"].get(wx.get("code"), ("—", "—"))
            d.text((MARGIN, 372), f"{round(wx['temp'])}°", font=bold(72),
                   fill=BLACK, anchor="la")
            # "Today" pairs the current reading with the day columns below,
            # which otherwise leave you counting days to work out what the big
            # number refers to.
            d.text((W - MARGIN, 378), s["today"], font=bold(22), fill=GREY, anchor="ra")
            d.text((W - MARGIN, 412), full, font=regular(26), fill=BLACK, anchor="ra")
            # min first, the same order as the day columns below, so the pair
            # reads identically everywhere without needing labels.
            if wx.get("tmin") is not None and wx.get("tmax") is not None:
                d.text((W - MARGIN, 460), f"{round(wx['tmin'])}° / {round(wx['tmax'])}°",
                       font=regular(22), fill=GREY, anchor="ra")
            _sun_line(d, 460, wx)
        else:
            d.text((MARGIN, 380), s["no_weather"], font=regular(24), fill=GREY, anchor="la")

        _rule(d, 510, fill=LIGHT)

        for i, cx in enumerate((116, 300, 484)):
            days = wx.get("days") or []
            if i >= len(days):
                continue
            day = days[i]
            name = t["weekdays"][date.fromisoformat(day["date"]).weekday()]
            _, short = t["wmo"].get(day["code"], ("—", "—"))
            d.text((cx, 552), name, font=bold(26), fill=BLACK, anchor="ma")
            d.text((cx, 598), f"{round(day['tmin'])}° / {round(day['tmax'])}°",
                   font=regular(24), fill=BLACK, anchor="ma")
            d.text((cx, 640), short, font=regular(20), fill=GREY, anchor="ma")
            # Only above 20%: a row of "0%" under clear days is noise. Black
            # while the condition stays grey, so it pulls the eye.
            pop = day.get("pop")
            if pop is not None and pop >= 20:
                d.text((cx, 680), f"☂ {round(pop)}%", font=bold(20),
                       fill=BLACK, anchor="ma")

    # --- footer ----------------------------------------------------------
    _rule(d, Y_WEATHER)

    named = [(s["host"], host)]
    for label, src in ((s["media"], media), (s["weather"], wx), (s["services"], kuma)):
        if src is not None:
            named.append((label, src))
    stale = [n for n, src in named if not src.get("ok") or src.get("stale")]
    right = (f"{s['stale']} " + ", ".join(stale) if stale
             else f"{s['updated']} {now.strftime('%H:%M')}")

    # A failing disk displaces uptime. Spelled out rather than a warning glyph:
    # U+26A0 is not reliably in DejaVu.
    smart = (media or {}).get("smart") or {}
    bad = smart.get("bad") or 0
    if bad:
        extra = f" +{bad - 1}" if bad > 1 else ""
        d.text((MARGIN, 762),
               f"SMART: {smart.get('worst') or '?'} {smart.get('errors') or 0} "
               f"{s['errors']}{extra}", font=bold(18), fill=BLACK, anchor="lm")
    elif host.get("ok"):
        d.text((MARGIN, 762), f"{s['uptime']} {_uptime(host['uptime'])}",
               font=regular(18), fill=GREY, anchor="lm")
    d.text((W - MARGIN, 762), right, font=regular(18),
           fill=BLACK if stale else GREY, anchor="rm")

    # Match the panel: 16 grey levels. Smaller file, and no dithering surprises.
    img = img.point(lambda p: (p // 17) * 17)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
