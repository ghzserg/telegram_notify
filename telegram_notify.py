# Telegram notifications for zmod, without Apprise
#
# Based on moonraker/components/notifier.py
# Copyright (C) 2022 Pataar <me@pataar.nl>
# Copyright (C) 2026 mlengle
#
# This file may be distributed under the terms of the GNU GPLv3 license.

from __future__ import annotations

import asyncio
import configparser
import logging
import re
import uuid
from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from ..common import JobEvent
from ..utils import json_wrapper as jsonw

# Annotation imports
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    Optional,
    Tuple,
)

if TYPE_CHECKING:
    from ..confighelper import ConfigHelper

API_URL = "https://api.telegram.org"
SETTINGS_FILE = "/opt/config/mod_data/telegram_notify.conf"
# Telegram limits, in UTF-16 code units
TEXT_MAXLEN = 4096
CAPTION_MAXLEN = 1024
TOKEN_RE = re.compile(r"^[0-9]+:[A-Za-z0-9_-]+$")
CHAT_ID_RE = re.compile(r"^(-?[0-9]+|@[A-Za-z0-9_]+)(?::([0-9]+))?$")
JOB_EVENTS = [str(e) for e in JobEvent if e != JobEvent.STANDBY]


def _truncate(text: str, maxlen: int) -> str:
    encoded = text.encode("utf-16-le")
    if len(encoded) <= 2 * maxlen:
        return text
    head = encoded[:2 * (maxlen - 1)].decode("utf-16-le", "ignore")
    return head + "…"


class TelegramNotify:
    def __init__(self, config: ConfigHelper) -> None:
        self.server = config.get_server()
        self.templates = self.server.load_component(config, "template")
        # The settings are read from a file of their own, not from the
        # Moonraker config: Moonraker writes its config with all values to
        # moonraker.log and returns it from /server/config.
        settings = self._read_settings()
        opts = settings["telegram_notify"]
        self.token = opts.get("bot_token", "").strip()
        self.name = opts.get("name", "").strip()
        self.snapshot_url = opts.get(
            "snapshot_url", "http://127.0.0.1:8080/?action=snapshot"
        ).strip()
        self.silent = self._option(opts, "silent", False)
        # Telegram's limit for photos is 10 MB
        self.max_photo_size = 1024 * self._option(
            opts, "max_photo_size", 2048, 64, 10240
        )
        self.max_queue = self._option(opts, "max_queue", 20, 1, 1000)
        self.targets: List[Dict[str, Any]] = []
        for entry in opts.get("chat_id", "").split(","):
            entry = entry.strip()
            if not entry:
                continue
            match = CHAT_ID_RE.match(entry)
            if match is None:
                self._warn(f"Invalid chat_id '{entry}'")
                continue
            chat_id, topic = match.groups()
            target: Dict[str, Any] = {"chat_id": chat_id}
            if topic is not None:
                target["message_thread_id"] = int(topic)
            self.targets.append(target)
        self.enabled = bool(TOKEN_RE.match(self.token)) and bool(self.targets)
        if not self.enabled:
            self._warn(
                "Telegram notifications are disabled, set bot_token and "
                "chat_id in mod_data/telegram_notify.conf and restart "
                "Moonraker"
            )

        # Messages for print job events: the plugin's defaults from the
        # Moonraker config, changed or added in the settings file
        messages: Dict[str, EventMessage] = {}
        for section in config.get_prefix_sections("telegram_notify "):
            try:
                msg = EventMessage.from_config(config[section])
            except Exception as e:
                self._warn(f"Invalid section [{section}]: {e}")
                continue
            messages[msg.name] = msg
        for section in settings.sections():
            parts = section.split(maxsplit=1)
            if len(parts) != 2 or parts[0] != "telegram_notify":
                continue
            try:
                msg = EventMessage.from_settings(
                    parts[1], settings[section], self.templates,
                    messages.get(parts[1])
                )
            except Exception as e:
                self._warn(f"Invalid section [{section}]: {e}")
                continue
            messages[msg.name] = msg
        self.messages: Dict[str, List[EventMessage]] = {}
        for msg in messages.values():
            events = JOB_EVENTS if "*" in msg.events else msg.events
            for event in events:
                if event not in JOB_EVENTS:
                    self._warn(
                        f"Unknown event '{event}' in [telegram_notify "
                        f"{msg.name}]"
                    )
                    continue
                self.messages.setdefault(event, []).append(msg)

        self.client: Optional[AsyncHTTPClient] = None
        self.lock = asyncio.Lock()
        self.pending = 0
        self.server.register_remote_method(
            "telegram_notify", self._remote_notify
        )
        self.server.register_event_handler(
            "job_state:state_changed", self._on_job_state_changed
        )

    def _warn(self, msg: str) -> None:
        self.server.add_warning(f"[telegram_notify]: {msg}")

    def _read_settings(self) -> configparser.ConfigParser:
        # Comments at the end of a line, as in Moonraker's config
        settings = configparser.ConfigParser(
            interpolation=None, inline_comment_prefixes=("#", ";")
        )
        try:
            with open(SETTINGS_FILE, encoding="utf-8") as f:
                settings.read_file(f)
        except Exception as e:
            # The error text would quote the line, maybe with the token
            line = getattr(e, "lineno", None)
            self._warn(
                f"Unable to read {SETTINGS_FILE}: {type(e).__name__}"
                + (f" in line {line}" if line else "")
            )
            settings = configparser.ConfigParser(interpolation=None)
        if not settings.has_section("telegram_notify"):
            settings.add_section("telegram_notify")
        return settings

    def _option(
        self, opts: configparser.SectionProxy, name: str, default: Any,
        minval: int = 0, maxval: int = 0
    ) -> Any:
        # A bool or int option, an invalid value warns and uses the default
        if name not in opts:
            return default
        try:
            if isinstance(default, bool):
                return opts.getboolean(name)
            val = int(opts[name])
            if not minval <= val <= maxval:
                raise ValueError(f"not between {minval} and {maxval}")
            return val
        except ValueError as e:
            self._warn(f"Invalid {name} '{opts[name]}' ({e}), using {default}")
            return default

    async def _on_job_state_changed(
        self, job_event: JobEvent, prev_stats: Dict[str, Any],
        new_stats: Dict[str, Any]
    ) -> None:
        event = str(job_event)
        context = {
            "event_name": event,
            "event_args": [prev_stats, new_stats],
            "event_message": ""
        }
        for msg in self.messages.get(event, []):
            try:
                text = msg.body.render(context)
            except Exception:
                logging.exception(
                    f"[telegram_notify {msg.name}]: Template error"
                )
                continue
            self.send(text, msg.photo)

    async def _remote_notify(self, message: str = "", photo: int = 0) -> None:
        self.send(str(message), bool(photo))

    def send(self, text: str, photo: bool = False) -> None:
        # Queues a notification, it is sent in the background
        if not self.enabled:
            return
        text = text.strip()
        if not text:
            return
        if self.name:
            text = f"{self.name}: {text}"
        if self.pending >= self.max_queue:
            logging.warning(
                "[telegram_notify]: Too many notifications waiting, "
                "dropping one"
            )
            return
        self.pending += 1
        self.server.get_event_loop().register_callback(
            self._send, text, photo
        )

    async def _send(self, text: str, photo: bool) -> None:
        # One notification at a time keeps the order and bounds the memory
        try:
            async with self.lock:
                image = await self._snapshot() if photo else None
                for target in self.targets:
                    try:
                        await self._send_to(target, text, image)
                    except Exception:
                        logging.exception(
                            f"[telegram_notify]: Notification to chat "
                            f"{target['chat_id']} failed"
                        )
        except Exception:
            logging.exception("[telegram_notify]: Notification failed")
        finally:
            self.pending -= 1

    async def _send_to(
        self, target: Dict[str, Any], text: str,
        image: Optional[Tuple[bytes, str]]
    ) -> None:
        fields = dict(target)
        if self.silent:
            fields["disable_notification"] = True
        if image is not None:
            if len(text.encode("utf-16-le")) <= 2 * CAPTION_MAXLEN:
                if await self._api("sendPhoto", dict(fields, caption=text),
                                   image):
                    return
            else:
                await self._api("sendPhoto", fields, image)
        # Text without a photo, or the photo was not accepted
        await self._api(
            "sendMessage", dict(fields, text=_truncate(text, TEXT_MAXLEN))
        )

    def _get_client(self) -> AsyncHTTPClient:
        # Own client: the shared one buffers responses up to 512 MB
        if self.client is None:
            limit = self.max_photo_size + 65536
            self.client = AsyncHTTPClient(
                force_instance=True, max_clients=2, max_body_size=limit,
                max_buffer_size=limit
            )
        return self.client

    async def _snapshot(self) -> Optional[Tuple[bytes, str]]:
        if not self.snapshot_url:
            return None
        error = ""
        try:
            resp = await self._get_client().fetch(HTTPRequest(
                self.snapshot_url, connect_timeout=5., request_timeout=10.
            ), raise_error=False)
        except Exception as e:
            # A snapshot over max_photo_size ends the download
            error = str(e) or type(e).__name__
        else:
            mime = resp.headers.get("Content-Type", "").split(";")[0].strip()
            if resp.code != 200:
                error = f"HTTP {resp.code}"
            elif not mime.startswith("image/"):
                error = f"not an image ({mime})"
            elif len(resp.body) > self.max_photo_size:
                # A body ending with the connection close (no length) is
                # truncated by the client's limit without an error
                error = "snapshot too large"
            else:
                return resp.body, mime
        logging.warning(f"[telegram_notify]: No webcam snapshot: {error}")
        return None

    async def _api(
        self, method: str, fields: Dict[str, Any],
        image: Optional[Tuple[bytes, str]] = None
    ) -> bool:
        # Calls a Bot API method, returns True on success
        if image is None:
            body = jsonw.dumps(fields)
            ctype = "application/json"
        else:
            body, ctype = self._multipart(fields, *image)
        code, desc = 0, ""
        for attempt in range(2):
            try:
                resp = await self._get_client().fetch(HTTPRequest(
                    f"{API_URL}/bot{self.token}/{method}", method="POST",
                    headers={"Content-Type": ctype}, body=body,
                    connect_timeout=5., request_timeout=30.
                ), raise_error=False)
                code = resp.code
                desc = "" if resp.error is None else str(resp.error)
                try:
                    result = jsonw.loads(resp.body)
                except Exception:
                    result = {}
            except Exception as e:
                code, desc, result = 0, str(e) or type(e).__name__, {}
            if code == 200:
                return True
            if not isinstance(result, dict):
                result = {}
            desc = str(result.get("description", desc))
            params = result.get("parameters")
            retry_after = (
                params.get("retry_after") if isinstance(params, dict)
                else None
            )
            if code == 429 and attempt == 0 and isinstance(retry_after, int):
                # Flood control, wait as asked by Telegram and retry once
                await asyncio.sleep(min(retry_after, 60))
                continue
            break
        logging.warning(
            f"[telegram_notify]: {method} to chat {fields['chat_id']} "
            f"failed: {desc.replace(self.token, '<token>')} (code {code})"
        )
        return False

    @staticmethod
    def _multipart(
        fields: Dict[str, Any], data: bytes, mime: str
    ) -> Tuple[bytes, str]:
        bnd = uuid.uuid4().hex
        ext = re.sub(r"[^a-z0-9]", "", mime.split("/")[-1].lower())
        ext = "jpg" if ext in ("jpeg", "") else ext
        parts = []
        for name, val in fields.items():
            val = str(val).lower() if isinstance(val, bool) else val
            parts.append(
                f'--{bnd}\r\nContent-Disposition: form-data; '
                f'name="{name}"\r\n\r\n{val}\r\n'.encode()
            )
        parts.append(
            f'--{bnd}\r\nContent-Disposition: form-data; name="photo"; '
            f'filename="snapshot.{ext}"\r\nContent-Type: {mime}\r\n\r\n'
            .encode()
        )
        parts.append(data)
        parts.append(f"\r\n--{bnd}--\r\n".encode())
        return b"".join(parts), f"multipart/form-data; boundary={bnd}"

    def close(self) -> None:
        if self.client is not None:
            self.client.close()
            self.client = None


class EventMessage:
    def __init__(
        self, name: str, events: List[str], body: Any, photo: bool
    ) -> None:
        self.name = name
        self.events = [e.strip().lower() for e in events if e.strip()]
        self.body = body
        self.photo = photo

    @classmethod
    def from_config(cls, config: ConfigHelper) -> EventMessage:
        return cls(
            config.get_name().split(maxsplit=1)[1],
            config.getlist("events", separator=","),
            config.gettemplate("body"), config.getboolean("photo", False)
        )

    @classmethod
    def from_settings(
        cls, name: str, opts: configparser.SectionProxy, templates: Any,
        default: Optional[EventMessage]
    ) -> EventMessage:
        # Options not given are taken from the plugin's message of that name
        if "events" in opts:
            events = opts["events"].split(",")
        elif default is not None:
            events = default.events
        else:
            raise ValueError("option 'events' is missing")
        if "body" in opts:
            body = templates.create_template(opts["body"].strip())
        elif default is not None:
            body = default.body
        else:
            raise ValueError("option 'body' is missing")
        if "photo" in opts:
            photo = opts.getboolean("photo")
        else:
            photo = default.photo if default is not None else False
        return cls(name, events, body, photo)


def load_component(config: ConfigHelper) -> TelegramNotify:
    return TelegramNotify(config)
