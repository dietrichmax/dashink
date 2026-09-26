#!/bin/sh
# Diagnostic for dashink. Tap from the library; output goes to the screen via
# sh_integration. Does not stop lab126_gui, so there is nothing to recover from.
#
# Reports panel geometry, whether wifi has an address, and whether the
# dashboard is reachable.

# ifconfig is in /sbin, which is on the framework's PATH but not on ssh's.
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH
export PATH

# The same override the loop reads, so this tests the URL the loop fetches.
[ -r /mnt/us/dashink.conf ] && eval "$(tr -d '\r' < /mnt/us/dashink.conf)"

URL="${DASHINK_URL:-http://dashink.lan:8099/dash.png}"

echo "--- display ---"
eips -i 2>&1
cat /sys/class/graphics/fb0/virtual_size 2>/dev/null

echo "--- network ---"
ifconfig wlan0 2>/dev/null | grep -i "inet addr" || echo "wlan0: no address"

echo "--- fetch $URL ---"
if command -v curl > /dev/null 2>&1; then
  curl -fsS -m 20 -o /tmp/dashink-test.png "$URL" \
    && echo "ok: $(wc -c < /tmp/dashink-test.png) bytes" \
    || echo "FAILED (curl exit $?)"
else
  wget -q -T 20 -O /tmp/dashink-test.png "$URL" \
    && echo "ok: $(wc -c < /tmp/dashink-test.png) bytes" \
    || echo "FAILED (wget exit $?)"
fi

echo "--- draw test ---"
[ -s /tmp/dashink-test.png ] && eips -g /tmp/dashink-test.png 2>&1 || echo "nothing to draw"
