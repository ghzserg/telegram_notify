#!/bin/sh
# Enables the telegram_notify plugin, called by ENABLE_PLUGIN

[ -f /opt/config/mod/.shell/0.sh ] && source /opt/config/mod/.shell/0.sh
[ -f /usr/data/zmod/zmod/.shell/0.sh ] && source /usr/data/zmod/zmod/.shell/0.sh

PLUGIN=/opt/config/mod_data/plugins/telegram_notify
FILE=/opt/config/mod_data/plugins.moonraker.conf
SETTINGS=/opt/config/mod_data/telegram_notify.conf

"${PLUGIN}/link.sh" || exit 1

L="${ZLANG}"
[ -d "${PLUGIN}/${L}" ] || L=en

# The settings are read by the plugin itself, they are not a part of the
# Moonraker config (which is written to moonraker.log)
[ -f "${SETTINGS}" ] || cp "${PLUGIN}/${L}/telegram_notify.conf" "${SETTINGS}"

touch "${FILE}"
sed -i '\|plugins/telegram_notify/|d; \|^\[include telegram_notify\.conf\]|d' "${FILE}"
[ -s "${FILE}" ] && [ -n "$(tail -c1 "${FILE}")" ] && echo >> "${FILE}"
echo "[include plugins/telegram_notify/${L}/telegram_notify.moonraker.cfg]" >> "${FILE}"

if grep -q "plugins/notify/" /opt/config/mod_data/plugins.cfg 2>/dev/null; then
    if [ "${ZLANG}" != 'ru' ]; then
        echo "The notify plugin is enabled too, disable one of them: DISABLE_PLUGIN name=notify"
    else
        echo "Плагин notify тоже включен, выключите один из них: DISABLE_PLUGIN name=notify"
    fi
fi

if [ "${ZLANG}" != 'ru' ]; then
    echo "Telegram notify installed. Settings: mod_data/telegram_notify.conf"
else
    echo "Telegram notify установлен. Настройки: mod_data/telegram_notify.conf"
fi
echo "REBOOT" >/tmp/printer
