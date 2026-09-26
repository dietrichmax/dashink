#!/bin/sh
# dashink display loop for a jailbroken Kindle (KT2, firmware 5.12.2.2).
#
# Install to /mnt/us/documents/. The Hotfix's sh_integration makes .sh files
# there tappable from the library, so this needs no launcher.
#
# WARNING: this stops the reader UI. Once lab126_gui is stopped the touchscreen
# does nothing, which includes the library entry for restore.sh. The only way
# back is `start lab126_gui` over SSH, or holding power ~20s. Have SSH working
# before you run this.

set -u

PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH
export PATH

# Overrides for any DASHINK_* below, kept out of this file because deploying
# overwrites it. eval through tr, not `.`: edited on Windows, a stray CR turns
# INTERVAL into a string that breaks sleep.
[ -r /mnt/us/dashink.conf ] && eval "$(tr -d '\r' < /mnt/us/dashink.conf)"

URL="${DASHINK_URL:-http://dashink.lan:8099/dash.png}"
INTERVAL="${DASHINK_INTERVAL:-300}"
OUT=/tmp/dashink.png

# Full refresh every Nth cycle to clear e-ink ghosting. 12 x 300s = hourly.
FULL_EVERY=12

fetch() {
  if command -v curl > /dev/null 2>&1; then
    curl -fs -m 20 -o "$1" "$URL" 2> /dev/null
  else
    wget -q -T 20 -O "$1" "$URL" 2> /dev/null
  fi
}

# Double-tapping the library entry starts two loops that fight over eips.
# PID file, not pgrep/flock — busybox here has neither.
LOCK=/tmp/dashink.pid
if [ -f "$LOCK" ] && kill -0 "$(cat "$LOCK" 2> /dev/null)" 2> /dev/null; then
  exit 0
fi
echo $$ > "$LOCK"

echo "$(date '+%Y-%m-%d %H:%M:%S') start url=$URL" >> /tmp/dashink.log

stop lab126_gui > /dev/null 2>&1
lipc-set-prop com.lab126.powerd preventScreenSaver 1 > /dev/null 2>&1

# The escape hatch, since stopping lab126_gui kills the touchscreen. event0 is
# max77696-onkey and carries only the power key, so any read means a press.
( dd if=/dev/input/event0 bs=16 count=1 > /dev/null 2>&1
  sh "$(dirname "$0")/restore.sh" ) &

# Silenced because sh_integration paints stdout onto the panel, and eips writes
# update_mode/wave_mode chatter on every call.
eips -c > /dev/null 2>&1
i=0
fails=0

while true; do
  fetch "$OUT.tmp"; rc=$?
  if [ "$rc" -eq 0 ] && [ -s "$OUT.tmp" ]; then
    mv "$OUT.tmp" "$OUT"
    fails=0
    i=$((i + 1))
    [ $((i % FULL_EVERY)) -eq 0 ] && eips -c > /dev/null 2>&1
    eips -g "$OUT" > /dev/null 2>&1
    # Re-asserted every cycle: powerd resets it on some firmware events, and a
    # screensaver that comes back blanks the panel with nothing to undo it.
    lipc-set-prop com.lab126.powerd preventScreenSaver 1 > /dev/null 2>&1
    sleep "$INTERVAL"
  else
    rm -f "$OUT.tmp"
    fails=$((fails + 1))
    cm=$(lipc-get-prop com.lab126.wifid cmState 2> /dev/null)
    # rc = curl/wget exit: 6 unresolved, 7 unreachable, 28 timeout, 0 empty.
    echo "$(date '+%Y-%m-%d %H:%M:%S') fetch failed ($fails) rc=$rc cm=$cm" >> /tmp/dashink.log

    # Nothing else asks the connection manager for a link while lab126_gui is
    # stopped. Every miss, not once: the wifi may be off for hours yet.
    [ "$cm" != CONNECTED ] && lipc-set-prop com.lab126.cmd ensureConnection wifi > /dev/null 2>&1

    # Back off once misses pile up. Capped at 2x so the panel still recovers
    # within ten minutes of the network returning.
    if [ "$fails" -ge 3 ]; then
      sleep $((INTERVAL * 2))
    else
      sleep "$INTERVAL"
    fi
  fi
done
