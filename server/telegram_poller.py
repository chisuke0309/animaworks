from __future__ import annotations
# AnimaWorks - Digital Anima Framework
# Copyright (C) 2026 AnimaWorks Authors
# SPDX-License-Identifier: Apache-2.0

"""Telegram long-polling integration for inbound message reception.

Polls the Telegram Bot API (getUpdates) in a background task and routes
messages from authorized users to the target anima's inbox via
Messenger.receive_external().  This mirrors the Slack Socket Mode pattern.
"""

import asyncio
import json
import logging
import os
from pathlib import Path

import httpx

from core.config.models import load_config
from core.paths import get_data_dir

logger = logging.getLogger("animaworks.telegram_poller")

_TELEGRAM_API_BASE = "https://api.telegram.org"
_OFFSET_FILE_NAME = "telegram_poll_offset.json"


class TelegramPollerManager:
    """Manages Telegram long-polling for inbound messages.

    Reads the bot token from the ``TELEGRAM_BOT_TOKEN`` environment variable
    and the authorized chat_id / target anima from config.json.
    """

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._token: str = ""
        self._authorized_chat_id: str = ""
        self._target_anima: str = "cicchi"
        self._offset: int = 0
        self._offset_path: Path = get_data_dir() / _OFFSET_FILE_NAME

    async def start(self) -> None:
        """Start the polling loop if Telegram is configured and enabled."""
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            logger.info("Telegram poller disabled (TELEGRAM_BOT_TOKEN not set)")
            return

        # Find Telegram channel config for authorized chat_id and target anima
        try:
            config = load_config()
            for channel in config.human_notification.channels:
                if channel.type == "telegram":
                    self._authorized_chat_id = str(channel.config.get("chat_id", ""))
                    self._target_anima = channel.config.get("target_anima", "cicchi")
                    break
        except Exception:
            logger.exception("Telegram poller: failed to load config")
            return

        if not self._authorized_chat_id:
            logger.info("Telegram poller disabled (chat_id not configured)")
            return

        self._token = token
        self._offset = self._load_offset()

        self._task = asyncio.create_task(self._poll_loop(), name="telegram-poller")
        logger.info(
            "Telegram poller started (authorized_chat_id=%s -> anima=%s)",
            self._authorized_chat_id, self._target_anima,
        )

    async def stop(self) -> None:
        """Stop the polling loop gracefully."""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Telegram poller stopped")

    # ── Internal ──────────────────────────────────────────────────────────

    def _load_offset(self) -> int:
        try:
            if self._offset_path.exists():
                data = json.loads(self._offset_path.read_text(encoding="utf-8"))
                return int(data.get("offset", 0))
        except Exception:
            pass
        return 0

    def _save_offset(self, offset: int) -> None:
        try:
            self._offset_path.write_text(
                json.dumps({"offset": offset}), encoding="utf-8"
            )
        except Exception:
            logger.debug("Telegram poller: failed to save offset", exc_info=True)

    async def _poll_loop(self) -> None:
        """Main long-polling loop. Uses timeout=20s for efficiency."""
        while True:
            try:
                updates = await self._get_updates(timeout=20)
                for update in updates:
                    await self._handle_update(update)
                    new_offset = update["update_id"] + 1
                    if new_offset > self._offset:
                        self._offset = new_offset
                        self._save_offset(self._offset)
            except asyncio.CancelledError:
                break
            except httpx.ReadTimeout:
                # Normal for long-polling — just retry immediately
                continue
            except Exception:
                logger.exception("Telegram poller error — retrying in 5s")
                await asyncio.sleep(5)

    async def _get_updates(self, timeout: int = 20) -> list[dict]:
        url = f"{_TELEGRAM_API_BASE}/bot{self._token}/getUpdates"
        params = {
            "offset": self._offset,
            "timeout": timeout,
            "limit": 100,
            "allowed_updates": ["message"],
        }
        async with httpx.AsyncClient(timeout=timeout + 10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
        return resp.json().get("result", [])

    async def _handle_update(self, update: dict) -> None:
        message = update.get("message")
        if not message:
            return

        chat_id = str(message.get("chat", {}).get("id", ""))
        text = (message.get("text") or "").strip()

        if not text:
            return

        if chat_id != self._authorized_chat_id:
            logger.warning(
                "Telegram poller: message from unauthorized chat_id=%s (ignored)", chat_id
            )
            return

        from_user = message.get("from", {})
        username = from_user.get("username") or from_user.get("first_name") or "user"
        message_id = str(message.get("message_id", ""))

        logger.info(
            "Telegram message received: from=%s -> anima=%s len=%d",
            username, self._target_anima, len(text),
        )

        try:
            from core.messenger import Messenger
            shared_dir = get_data_dir() / "shared"
            messenger = Messenger(shared_dir, self._target_anima)
            messenger.receive_external(
                content=text,
                source="telegram",
                source_message_id=message_id,
                external_user_id=username,
                external_channel_id=chat_id,
            )
        except Exception:
            logger.exception(
                "Telegram poller: failed to route message to anima=%s", self._target_anima
            )
