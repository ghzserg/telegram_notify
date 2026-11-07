#!/bin/sh
# Disables the telegram_notify plugin, called by DISABLE_PLUGIN.
# The settings in mod_data/telegram_notify.conf are kept.

[ -f /opt/config/mod/.shell/0.sh ] && source /opt/config/mod/.shell/0.sh
[ -f /usr/data/zmod/zmod/.shell/0.sh ] && source /usr/data/zmod/zmod/.shell/0.sh

MOONRAKER=/usr/data/zmod/moonraker
FILE=/opt/config/mod_data/plugins.moonraker.conf

[ -f "${FILE}" ] && sed -i '\|plugins/telegram_notify/|d; \|^\[include telegram_notify\.conf\]|d' "${FILE}"

rm -f "${MOONRAKER}/components/telegram_notify.py" \
      "${MOONRAKER}"/components/__pycache__/telegram_notify.*.pyc
[ -f "${MOONRAKER}/.git/info/exclude" ] && \
    sed -i '\|^/components/telegram_notify\.py$|d' "${MOONRAKER}/.git/info/exclude"

if [ "${ZLANG}" != 'ru' ]; then
    echo "Telegram notify uninstalled"
else
    echo "Telegram notify удалён"
fi
echo "REBOOT" >/tmp/printer
