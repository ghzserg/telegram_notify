#!/bin/sh
# Links the Moonraker component of the plugin. Moonraker loads components
# only from its own directory; the link is excluded from git, so the update
# manager does not see a dirty repo.

MOONRAKER=/usr/data/zmod/moonraker
LINK="${MOONRAKER}/components/telegram_notify.py"

if ! [ -d "${MOONRAKER}/components" ]; then
    echo "Moonraker not found in ${MOONRAKER}"
    exit 1
fi
ln -sfn /opt/config/mod_data/plugins/telegram_notify/telegram_notify.py "${LINK}" || exit 1

if [ -d "${MOONRAKER}/.git" ]; then
    EXCLUDE="${MOONRAKER}/.git/info/exclude"
    mkdir -p "${MOONRAKER}/.git/info"
    if ! grep -qxF "/components/telegram_notify.py" "${EXCLUDE}" 2>/dev/null; then
        [ -s "${EXCLUDE}" ] && [ -n "$(tail -c1 "${EXCLUDE}")" ] && echo >> "${EXCLUDE}"
        echo "/components/telegram_notify.py" >> "${EXCLUDE}"
    fi
fi
exit 0
