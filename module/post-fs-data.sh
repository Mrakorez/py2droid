# shellcheck shell=busybox
#
# shellcheck disable=1091
. /data/adb/py2droid/env.sh

cd "${0%/*}" || exit 1
exec python3 update-bin.py
