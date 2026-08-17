#!/bin/sh
# Stop the dashboard loop and bring the reader UI back.
#
# The escape hatch for dashink.sh, which stops lab126_gui and leaves the
# touchscreen dead, including this file's own library entry.
set -u

# `start` is in /sbin, which is on the framework's PATH but not on ssh's.
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH
export PATH

for d in /proc/[0-9]*; do
  [ -r "$d/cmdline" ] || continue
  case "$(tr '\0' ' ' < "$d/cmdline")" in
    *dashink.sh*) kill "${d#/proc/}" 2> /dev/null ;;
  esac
done

rm -f /tmp/dashink.pid

lipc-set-prop com.lab126.powerd preventScreenSaver 0 > /dev/null 2>&1
eips -c > /dev/null 2>&1
start lab126_gui > /dev/null 2>&1
