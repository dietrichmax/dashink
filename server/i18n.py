"""Language selection.

The catalogues themselves live in lang/, one module per language. This is the
only i18n module render.py imports: it picks a language and fills the gaps.
"""

from lang import CATALOGUES

DEFAULT = "en"


def _seven(names, fallback):
    """Weekday names are indexed by weekday(), so a short list raises on
    whichever day falls off the end, a bug that waits days to appear."""
    return names if len(names) == 7 else fallback


def catalogue(lang):
    """Everything render.py needs for one language.

    Each table falls back to English on its own, so a half-finished translation
    renders with English gaps. render.py subscripts these directly, so a
    KeyError here 500s /dash.png and the Kindle draws nothing.
    """
    base = CATALOGUES[DEFAULT]
    mod = CATALOGUES.get(lang, base)
    # getattr rather than mod.WMO: a translation in progress is likely to omit a
    # whole table, and attribute access would raise instead of falling back.
    return {
        "s": {**base.STRINGS, **getattr(mod, "STRINGS", {})},
        "wmo": {**base.WMO, **getattr(mod, "WMO", {})},
        "weekdays": _seven(getattr(mod, "WEEKDAYS", ()), base.WEEKDAYS),
        "weekdays_long": _seven(getattr(mod, "WEEKDAYS_LONG", ()), base.WEEKDAYS_LONG),
    }
