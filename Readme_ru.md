# Telegram Notify

Плагин [Z-Mod](https://github.com/ghzserg/zmod): уведомления о печати в Telegram без библиотеки Apprise.

Moonraker сам отправляет сообщения в Telegram Bot API. Apprise загружает все свои плагины и занимает несколько мегабайт памяти Moonraker, а на принтерах со 128 МБ RAM каждый мегабайт заметен.

Память Moonraker (RssAnon) на Flashforge AD5M с Z-Mod:

| | RssAnon |
| :--- | ---: |
| notify (Apprise) | 30.3 МБ |
| telegram_notify | 24.7 МБ |
| без уведомлений | 24.2 МБ |

Экономия около 5.6 МБ по сравнению с notify, сам плагин добавляет около 0.5 МБ.

Плагин умеет то же, что и [notify](https://github.com/ghzserg/notify/blob/main/Readme_ru.md) для Telegram: уведомления о старте, окончании, ошибке, отмене, паузе и продолжении печати, сообщения от Z-Mod (датчики филамента, включение принтера), прогресс в процентах, снимок с камеры. Другие сервисы, кроме Telegram, не поддерживаются: для них используйте notify.

Не включайте notify и telegram_notify одновременно: макрос `_NOTIFY` будет работать только у одного из них.

## Установка

Пока плагина нет в списке Z-Mod, добавьте в `mod_data/user.moonraker.conf`:

```
[update_manager telegram_notify]
type: git_repo
channel: dev
path: /root/printer_data/config/mod_data/plugins/telegram_notify
origin: https://github.com/mlengle/telegram_notify.git
is_system_service: False
primary_branch: main
```

Затем выполните `ENABLE_PLUGIN name=telegram_notify`. Принтер перезагрузится.

Если раньше использовался notify, выключите его (`DISABLE_PLUGIN name=notify`) и удалите из `mod_data/user.moonraker.conf` свои секции `[notifier ...]`, если они есть (например, `events: none` для отключённых событий). Пока в конфигурации Moonraker есть хоть одна секция `[notifier ...]`, он загружает Apprise. Отключить сообщение в telegram_notify можно в `mod_data/telegram_notify.conf`:

```
[telegram_notify print_resumed]
events: none
```

## Настройка

1. Создайте бота у [@BotFather](https://t.me/BotFather) и получите токен.
2. Напишите боту любое сообщение и узнайте номер чата, например у [@userinfobot](https://t.me/userinfobot).
3. Пропишите `bot_token` и `chat_id` в `mod_data/telegram_notify.conf`.
4. Перезапустите Moonraker или принтер.

Остальные параметры описаны в самом файле: имя принтера в начале сообщений, отправка без звука, адрес снимка, наибольший размер снимка, длина очереди. В `chat_id` можно указать несколько чатов через запятую и тему форума как `chat_id:topic_id`.

Плагин читает `mod_data/telegram_notify.conf` сам, этот файл не входит в конфигурацию Moonraker, поэтому токен бота не попадает в `moonraker.log`.

Тексты уведомлений о печати по умолчанию находятся в `mod_data/plugins/telegram_notify/ru/telegram_notify.moonraker.cfg`. Не меняйте этот файл: изменения потеряются при обновлении плагина. Чтобы изменить сообщение, добавьте в `mod_data/telegram_notify.conf` секцию с тем же именем и нужными параметрами, например:

```
[telegram_notify print_start]
body: Начата печать {event_args[1].filename}
photo: False
```

Новое сообщение добавляется так же, под своим именем. Параметры: `events` (`started`, `complete`, `error`, `cancelled`, `paused`, `resumed`, `*` для всех или `none`, чтобы выключить сообщение), `body` (шаблон, как в `[notifier]` Moonraker: `event_name`, `event_args`) и `photo`.

## Макросы

- `TELEGRAM_NOTIFY MSG="текст" PHOTO=1` — отправить сообщение, `PHOTO=1` добавляет снимок с камеры.
- `_NOTIFY MSG="текст" PHOTO=0 TYPE=...` — вызывается Z-Mod, работает так же, как в notify.

Настройки Z-Mod общие с notify:

- `SAVE_VARIABLE VARIABLE=notify_percent VALUE=5` — уведомлять о прогрессе каждые 5 процентов (0 — выключить).
- `SAVE_VARIABLE VARIABLE=notify_photo VALUE=0` — не отправлять снимки в сообщениях `_NOTIFY`.

## Ограничения Telegram

- Длинный текст обрезается до 4096 символов, подпись к снимку — до 1024 символов (длинный текст отправляется отдельным сообщением).
- Если Telegram просит подождать (слишком частые сообщения), плагин ждёт и повторяет отправку один раз.
- Сообщения отправляются по одному. Если в очереди больше `max_queue` сообщений, новые отбрасываются с предупреждением в `moonraker.log`.

## Удаление

`DISABLE_PLUGIN name=telegram_notify`. Файл настроек `mod_data/telegram_notify.conf` сохраняется.
