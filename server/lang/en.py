"""English. The default, and the fallback for every other language."""

STRINGS = {
    'date': '%d/%m/%Y',
    'weather': 'WEATHER',
    'services': 'SERVICES',
    'media': 'MEDIA',
    'host': 'HOST',
    'today': 'Today',
    'na': 'n/a',
    'no_host_data': 'no data from host',
    'no_weather': 'no weather data',
    'no_connection': 'not reachable',
    'all_up': 'all up',
    'n_down': '{n} unreachable',
    'free': 'free',
    'cores': 'cores',
    'uptime': 'uptime',
    'updated': 'updated',
    'stale': 'stale:',
    'errors': 'errors',
    'decimal': '.',
}

WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

WEEKDAYS_LONG = [
    'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday',
    'Sunday'
]

WMO = {
    0: ('Clear', 'Clear'),
    1: ('Mostly clear', 'Clear'),
    2: ('Partly cloudy', 'Cloudy'),
    3: ('Overcast', 'Overcast'),
    45: ('Fog', 'Fog'),
    48: ('Freezing fog', 'Fog'),
    51: ('Light drizzle', 'Drizzle'),
    53: ('Drizzle', 'Drizzle'),
    55: ('Heavy drizzle', 'Drizzle'),
    56: ('Freezing drizzle', 'Drizzle'),
    57: ('Freezing drizzle', 'Drizzle'),
    61: ('Light rain', 'Rain'),
    63: ('Rain', 'Rain'),
    65: ('Heavy rain', 'Rain'),
    66: ('Freezing rain', 'Rain'),
    67: ('Freezing rain', 'Rain'),
    71: ('Light snow', 'Snow'),
    73: ('Snow', 'Snow'),
    75: ('Heavy snow', 'Snow'),
    77: ('Snow grains', 'Snow'),
    80: ('Showers', 'Showers'),
    81: ('Showers', 'Showers'),
    82: ('Heavy showers', 'Showers'),
    85: ('Snow showers', 'Snow'),
    86: ('Snow showers', 'Snow'),
    95: ('Thunderstorm', 'Storm'),
    96: ('Thunderstorm, hail', 'Storm'),
    99: ('Thunderstorm, hail', 'Storm'),
}
