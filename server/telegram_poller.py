from __future__ import annotations
# AnimaWorks - Digital Anima Framework
# Copyright (C) 2026 AnimaWorks Authors
# SPDX-License-Identifier: Apache-2.0

"""Telegram long-polling integration for inbound message reception.

Polls the Telegram Bot API (getUpdates) in a background task and routes
messages from authorized users to the target anima's inbox via
Messenger.receive_external().  Supports multiple bots (one per anima).
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


class _TelegramBotPoller:
    """Polls a single Telegram bot and routes messages to its target anima."""

    def __init__(
        self, token: str, authorized_chat_id: str, target_anima: str, label: str,
    ) -> None:
        self._token = token
        self._authorized_chat_id = authorized_chat_id
        self._target_anima = target_anima
        self._label = label
        self._task: asyncio.Task | None = None
        self._offset: int = 0
        self._offset_path = get_data_dir() / f"telegram_poll_offset_{target_anima}.json"

    async def start(self) -> None:
        self._offset = self._load_offset()
        self._task = asyncio.create_task(
            self._poll_loop(), name=f"telegram-poller-{self._target_anima}"
        )
        logger.info(
            "Telegram poller started (authorized_chat_id=%s -> anima=%s)",
            self._authorized_chat_id, self._target_anima,
        )

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Telegram poller stopped for %s", self._target_anima)

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
                continue
            except Exception:
                logger.exception("Telegram poller error (%s) — retrying in 5s", self._label)
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
                "Telegram poller (%s): message from unauthorized chat_id=%s (ignored)",
                self._label, chat_id,
            )
            return

        from_user = message.get("from", {})
        username = from_user.get("username") or from_user.get("first_name") or "user"
        message_id = str(message.get("message_id", ""))

        logger.info(
            "Telegram message received: from=%s -> anima=%s len=%d",
            username, self._target_anima, len(text),
        )

        # Check for approval command (OK / ok / 承認)
        if text.lower() in ("ok", "承認"):
            await self._handle_approval_reply(chat_id, text)
            return

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

    async def _handle_approval_reply(self, chat_id: str, text: str) -> None:
        """Approve the most recent pending post when user replies OK."""
        try:
            from core.tools.x_post import PENDING_DIR

            if not PENDING_DIR.exists():
                await self._send_message(chat_id, "承認対象の投稿がありません。")
                return

            pending_files = sorted(
                (f for f in PENDING_DIR.glob("*.json")),
                key=lambda f: f.stat().st_mtime,
                reverse=True,
            )

            approved = None
            for fp in pending_files:
                try:
                    data = json.loads(fp.read_text(encoding="utf-8"))
                    if data.get("status") == "pending":
                        data["status"] = "approved"
                        fp.write_text(
                            json.dumps(data, ensure_ascii=False, indent=2),
                            encoding="utf-8",
                        )
                        approved = data
                        logger.info("Telegram approval: %s", data.get("id", fp.stem))
                        break
                except (json.JSONDecodeError, OSError):
                    continue

            if approved:
                preview = approved.get("text", "")[:100]
                await self._send_message(
                    chat_id,
                    f"✅ 承認しました: {approved.get('id', '?')}\n{preview}…",
                )
            else:
                await self._send_message(chat_id, "承認待ちの投稿がありません。")
        except Exception:
            logger.exception("Telegram approval handler failed")
            await self._send_message(chat_id, "承認処理中にエラーが発生しました。")

    async def _send_message(self, chat_id: str, text: str) -> None:
        url = f"{_TELEGRAM_API_BASE}/bot{self._token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text[:4096]}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
        except Exception:
            logger.warning("Failed to send Telegram reply to %s", chat_id, exc_info=True)


class TelegramPollerManager:
    """Manages multiple Telegram bot pollers (one per configured channel)."""

    def __init__(self) -> None:
        self._pollers: list[_TelegramBotPoller] = []

    async def start(self) -> None:
        try:
            config = load_config()
        except Exception:
            logger.exception("Telegram poller: failed to load config")
            return

        for channel in config.human_notification.channels:
            if channel.type != "telegram" or not channel.enabled:
                continue

            token_env = channel.config.get("bot_token_env", "TELEGRAM_BOT_TOKEN")
            token = os.environ.get(token_env, "").strip()
            if not token:
                logger.info(
                    "Telegram poller disabled for %s (%s not set)",
                    channel.config.get("target_anima", "?"), token_env,
                )
                continue

            chat_id = str(channel.config.get("chat_id", ""))
            target_anima = channel.config.get("target_anima", "cicchi")

            if not chat_id:
                logger.info(
                    "Telegram poller disabled for %s (chat_id not configured)", target_anima,
                )
                continue

            poller = _TelegramBotPoller(
                token=token,
                authorized_chat_id=chat_id,
                target_anima=target_anima,
                label=f"{target_anima}({token_env})",
            )
            await poller.start()
            self._pollers.append(poller)

        if not self._pollers:
            logger.info("No Telegram pollers started")

    async def stop(self) -> None:
        for poller in self._pollers:
            await poller.stop()
        self._pollers.clear()
        logger.info("Telegram poller manager stopped")
