"""German."""

STRINGS = {
    'date': '%d.%m.%Y',
    'weather': 'WETTER',
    'services': 'SERVICES',
    'media': 'MEDIA',
    'host': 'HOST',
    'today': 'Heute',
    'na': 'n/v',
    'no_host_data': 'keine Daten vom Host',
    'no_weather': 'keine Wetterdaten',
    'no_connection': 'keine Verbindung',
    'all_up': 'alle erreichbar',
    'n_down': '{n} nicht erreichbar',
    'free': 'frei',
    'cores': 'Kerne',
    'uptime': 'uptime',
    'updated': 'aktualisiert',
    'stale': 'veraltet:',
    'errors': 'Fehler',
    'decimal': ',',
}

WEEKDAYS = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']

WEEKDAYS_LONG = [
    'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag',
    'Sonntag'
]

WMO = {
    0: ('Klar', 'Klar'),
    1: ('Überwiegend klar', 'Klar'),
    2: ('Teils bewölkt', 'Wolkig'),
    3: ('Bedeckt', 'Bedeckt'),
    45: ('Nebel', 'Nebel'),
    48: ('Reifnebel', 'Nebel'),
    51: ('Leichter Niesel', 'Niesel'),
    53: ('Niesel', 'Niesel'),
    55: ('Starker Niesel', 'Niesel'),
    56: ('Gefrierender Niesel', 'Niesel'),
    57: ('Gefrierender Niesel', 'Niesel'),
    61: ('Leichter Regen', 'Regen'),
    63: ('Regen', 'Regen'),
    65: ('Starker Regen', 'Regen'),
    66: ('Gefrierender Regen', 'Regen'),
    67: ('Gefrierender Regen', 'Regen'),
    71: ('Leichter Schnee', 'Schnee'),
    73: ('Schnee', 'Schnee'),
    75: ('Starker Schnee', 'Schnee'),
    77: ('Schneegriesel', 'Schnee'),
    80: ('Schauer', 'Schauer'),
    81: ('Schauer', 'Schauer'),
    82: ('Starke Schauer', 'Schauer'),
    85: ('Schneeschauer', 'Schnee'),
    86: ('Schneeschauer', 'Schnee'),
    95: ('Gewitter', 'Gewitter'),
    96: ('Gewitter mit Hagel', 'Gewitter'),
    99: ('Gewitter mit Hagel', 'Gewitter'),
}
