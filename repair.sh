#!/bin/sh
# Called at every Klipper start: when the link of the Moonraker component
# is missing (e.g. Moonraker was reinstalled), restores it and restarts
# Moonraker.

[ -f /opt/config/mod/.shell/0.sh ] && source /opt/config/mod/.shell/0.sh
[ -f /usr/data/zmod/zmod/.shell/0.sh ] && source /usr/data/zmod/zmod/.shell/0.sh

LINK=/usr/data/zmod/moonraker/components/telegram_notify.py
[ -L "${LINK}" ] && [ -e "${LINK}" ] && exit 0

/opt/config/mod_data/plugins/telegram_notify/link.sh || exit 1
echo "telegram_notify: Moonraker component link restored, restarting Moonraker"

# One attempt with a timeout: this script holds Klipper's command queue.
# When Moonraker is not running yet, it loads the component on its start.
URL=http://127.0.0.1:7125/server/restart
if [ -x "${CURL}" ]; then
    "${CURL}" -s -f -m 10 -X POST "${URL}" >/dev/null && exit 0
elif command -v curl >/dev/null; then
    curl -s -f -m 10 -X POST "${URL}" >/dev/null && exit 0
else
    wget -q -T 10 -O /dev/null --post-data= "${URL}" && exit 0
fi
echo "telegram_notify: restart Moonraker to enable the notifications"
exit 0
