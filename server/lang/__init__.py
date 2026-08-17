"""Language catalogues, one module per language.

To add a language: copy en.py, translate it, and add it to CATALOGUES below.
Nothing else in the codebase needs to change. i18n.catalogue() fills anything
you leave out from English, so a half-finished translation still renders.

Each module provides four names:

  STRINGS        the short labels. "date" is a strftime format and "decimal"
                 is the separator for temperatures. Numeric date formats only.
  WEEKDAYS       seven short names, Monday first, to match date.weekday().
  WEEKDAYS_LONG  the same seven spelled out, for the header.
  WMO            weather code -> (full label, short label). The short form has
                 to fit a 184px column at 20px, so it collapses intensity.

Plain dicts rather than gettext: ~20 short strings do not need a .po toolchain.
"""

from . import de, en

CATALOGUES = {"en": en, "de": de}
