# Telegram Notify

A [Z-Mod](https://github.com/ghzserg/zmod) plugin: print notifications to Telegram without the Apprise library.

Moonraker sends the messages to the Telegram Bot API itself. Apprise loads all of its plugins and takes several megabytes of Moonraker's memory, which matters on printers with 128 MB of RAM.

Moonraker memory (RssAnon) on a Flashforge AD5M with Z-Mod:

| | RssAnon |
| :--- | ---: |
| notify (Apprise) | 30.3 MB |
| telegram_notify | 24.7 MB |
| no notifications | 24.2 MB |

About 5.6 MB less than with notify, the plugin itself adds about 0.5 MB.

For Telegram it does what the [notify](https://github.com/ghzserg/notify) plugin does: notifications when a print starts, finishes, fails, is canceled, paused or resumed, messages from Z-Mod (filament sensors, printer on), progress in percent, a webcam snapshot. Services other than Telegram are not supported, use notify for them.

Do not enable notify and telegram_notify at the same time: the `_NOTIFY` macro works for only one of them.

## Installation

Until the plugin is in the Z-Mod plugin list, add to `mod_data/user.moonraker.conf`:

```
[update_manager telegram_notify]
type: git_repo
channel: dev
path: /root/printer_data/config/mod_data/plugins/telegram_notify
origin: https://github.com/mlengle/telegram_notify.git
is_system_service: False
primary_branch: main
```

Then run `ENABLE_PLUGIN name=telegram_notify`. The printer reboots.

When switching from notify, disable it (`DISABLE_PLUGIN name=notify`) and remove your own `[notifier ...]` sections from `mod_data/user.moonraker.conf`, if any (e.g. `events: none` for events turned off). As long as the Moonraker config has a `[notifier ...]` section, Moonraker loads Apprise. A message of telegram_notify is turned off in `mod_data/telegram_notify.conf`:

```
[telegram_notify print_resumed]
events: none
```

## Settings

1. Create a bot with [@BotFather](https://t.me/BotFather) and get its token.
2. Send the bot any message and find your chat id, e.g. with [@userinfobot](https://t.me/userinfobot).
3. Set `bot_token` and `chat_id` in `mod_data/telegram_notify.conf`.
4. Restart Moonraker or the printer.

The other options are described in that file: printer name in front of the messages, silent messages, snapshot url, largest snapshot, queue length. `chat_id` takes several chats separated by commas, a forum topic as `chat_id:topic_id`.

The plugin reads `mod_data/telegram_notify.conf` itself, the file is not a part of the Moonraker config, so the bot token does not end up in `moonraker.log`.

The default print notification texts are in `mod_data/plugins/telegram_notify/en/telegram_notify.moonraker.cfg`. Do not edit that file, the changes are lost when the plugin is updated. To change a message, add a section with the same name and the options to change to `mod_data/telegram_notify.conf`, e.g.:

```
[telegram_notify print_start]
body: Started {event_args[1].filename}
photo: False
```

A new message is added the same way, under a name of its own. Options: `events` (`started`, `complete`, `error`, `cancelled`, `paused`, `resumed`, `*` for all or `none` to turn the message off), `body` (a template as in Moonraker's `[notifier]`: `event_name`, `event_args`) and `photo`.

## Macros

- `TELEGRAM_NOTIFY MSG="text" PHOTO=1` — send a message, `PHOTO=1` adds a webcam snapshot.
- `_NOTIFY MSG="text" PHOTO=0 TYPE=...` — called by Z-Mod, works as in notify.

Z-Mod settings shared with notify:

- `SAVE_VARIABLE VARIABLE=notify_percent VALUE=5` — progress every 5 percent (0 turns it off).
- `SAVE_VARIABLE VARIABLE=notify_photo VALUE=0` — no snapshots in `_NOTIFY` messages.

## Telegram limits

- Long text is cut at 4096 characters, a snapshot caption at 1024 (a longer text is sent as a separate message).
- When Telegram asks to wait (too many messages), the plugin waits and retries once.
- Messages are sent one at a time. With more than `max_queue` waiting, new ones are dropped with a warning in `moonraker.log`.

## Removal

`DISABLE_PLUGIN name=telegram_notify`. The settings file `mod_data/telegram_notify.conf` is kept.
