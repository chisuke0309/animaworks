from __future__ import annotations
# AnimaWorks - Digital Anima Framework
# Copyright (C) 2026 AnimaWorks Authors
# SPDX-License-Identifier: Apache-2.0

"""Telegram Bot API notification channel."""

import html
import logging
from pathlib import Path
from typing import Any

import httpx

from core.notification.notifier import NotificationChannel, register_channel

logger = logging.getLogger("animaworks.notification.telegram")

_TELEGRAM_API_BASE = "https://api.telegram.org"


@register_channel("telegram")
class TelegramChannel(NotificationChannel):
    """Send notifications via Telegram Bot API."""

    @property
    def channel_type(self) -> str:
        return "telegram"

    async def send(
        self,
        subject: str,
        body: str,
        priority: str = "normal",
        *,
        anima_name: str = "",
        attachments: list[str] | None = None,
    ) -> str:
        token = self._resolve_env("bot_token_env")
        if not token:
            return "telegram: ERROR - bot_token_env not configured or env var not set"

        chat_id = self._config.get("chat_id", "")
        if not chat_id:
            return "telegram: ERROR - chat_id not configured"

        prefix = f"[{priority.upper()}] " if priority in ("high", "urgent") else ""
        safe_subject = html.escape(subject)
        safe_body = html.escape(body)
        text = f"{prefix}<b>{safe_subject}</b>\n\n{safe_body}"

        url = f"{_TELEGRAM_API_BASE}/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text[:4096],
            "parse_mode": "HTML",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()

                # Send image attachments if provided
                if attachments:
                    await self._send_images(client, token, chat_id, attachments)

            logger.info("Telegram notification sent: %s", subject[:50])
            return "telegram: OK"
        except httpx.HTTPStatusError as e:
            msg = f"telegram: ERROR - HTTP {e.response.status_code}"
            logger.error(msg)
            return msg
        except Exception as e:
            msg = f"telegram: ERROR - {e}"
            logger.error(msg)
            return msg

    async def _send_images(
        self,
        client: httpx.AsyncClient,
        token: str,
        chat_id: str,
        image_paths: list[str],
    ) -> None:
        """Send images as a media group (album) via Telegram."""
        import json

        valid_paths = [p for p in image_paths if Path(p).is_file()]
        if not valid_paths:
            logger.warning("No valid image files to send")
            return

        if len(valid_paths) <= 10:
            # Send as media group (album) — up to 10 images
            url = f"{_TELEGRAM_API_BASE}/bot{token}/sendMediaGroup"
            media = []
            files = {}
            for i, path in enumerate(valid_paths):
                attach_name = f"photo{i}"
                media.append({
                    "type": "photo",
                    "media": f"attach://{attach_name}",
                })
                files[attach_name] = (
                    Path(path).name,
                    open(path, "rb"),
                    "image/jpeg",
                )

            try:
                resp = await client.post(
                    url,
                    data={"chat_id": chat_id, "media": json.dumps(media)},
                    files=files,
                    timeout=60.0,
                )
                resp.raise_for_status()
                logger.info("Telegram media group sent: %d images", len(valid_paths))
            except Exception as e:
                logger.error("Failed to send media group: %s", e)
            finally:
                for f in files.values():
                    f[1].close()
