from __future__ import annotations
# AnimaWorks - Digital Anima Framework
# Copyright (C) 2026 AnimaWorks Authors
# SPDX-License-Identifier: Apache-2.0

"""Ticket Manager — outbox-based reliable messaging with acknowledgment.

Manages the lifecycle of inter-Anima messages via an outbox/ticket pattern:

1. A sends to B → message placed in A's outbox (addressed to B)
2. B picks up message → leaves an acknowledgment ticket
3. B completes work → places response in B's outbox (addressed to A)
4. A picks up response → cycle complete

The TicketManager runs as a single server-level background task,
monitoring all outboxes for timeouts and triggering alerts.
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("animaworks.ticket_manager")

# ── Constants ─────────────────────────────────────────────
_POLL_INTERVAL_SEC = 30       # How often to check outboxes
_PICKUP_TIMEOUT_SEC = 5 * 60  # 5 min: alert if message not picked up

# Ticket statuses
STATUS_PENDING = "pending"       # Message placed in outbox, awaiting pickup
STATUS_RESOLVED = "resolved"     # Recipient picked up message (= resolved)
STATUS_TIMEOUT = "timeout"       # Timed out waiting for pickup


class TicketManager:
    """Server-level manager for outbox tickets across all Animas.

    Runs a single polling loop that monitors ``shared/outbox/{anima}/``
    for all Animas, detects timeouts, and sends Telegram alerts.
    """

    def __init__(self, shared_dir: Path) -> None:
        self._shared_dir = shared_dir
        self._outbox_root = shared_dir / "outbox"
        self._outbox_root.mkdir(parents=True, exist_ok=True)
        self._task: asyncio.Task | None = None
        self._shutdown = asyncio.Event()

    # ── Lifecycle ──────────────────────────────────────────

    async def start(self) -> None:
        """Start the ticket monitoring loop."""
        self._shutdown.clear()
        self._task = asyncio.create_task(
            self._monitor_loop(), name="ticket-manager",
        )
        logger.info("Ticket manager started")

    async def stop(self) -> None:
        """Stop the monitoring loop gracefully."""
        self._shutdown.set()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Ticket manager stopped")

    # ── Outbox operations (called by Messenger) ───────────

    @staticmethod
    def create_ticket(
        outbox_root: Path,
        from_anima: str,
        to_anima: str,
        message_id: str,
        intent: str,
        content_preview: str,
    ) -> Path:
        """Create a new ticket in the sender's outbox.

        Called by Messenger.send() when sending to another Anima.
        Returns the ticket file path.
        """
        outbox_dir = outbox_root / from_anima
        outbox_dir.mkdir(parents=True, exist_ok=True)

        ticket = {
            "message_id": message_id,
            "from": from_anima,
            "to": to_anima,
            "intent": intent,
            "content_preview": content_preview[:200],
            "status": STATUS_PENDING,
            "created_at": time.time(),
            "picked_up_at": None,
            "resolved_at": None,
        }

        filename = f"{message_id}.ticket.json"
        filepath = outbox_dir / filename
        filepath.write_text(
            json.dumps(ticket, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.debug("Ticket created: %s -> %s (%s)", from_anima, to_anima, message_id)
        return filepath

    @staticmethod
    def resolve_ticket(
        outbox_root: Path,
        from_anima: str,
        message_id: str,
    ) -> bool:
        """Mark a ticket as resolved (message picked up by recipient).

        Called when a recipient reads a message from their inbox.
        Pickup = resolved in the simplified ticket model.
        """
        ticket_path = outbox_root / from_anima / f"{message_id}.ticket.json"
        if not ticket_path.exists():
            return False

        try:
            ticket = json.loads(ticket_path.read_text(encoding="utf-8"))
            if ticket["status"] == STATUS_PENDING:
                ticket["status"] = STATUS_RESOLVED
                ticket["resolved_at"] = time.time()
                ticket_path.write_text(
                    json.dumps(ticket, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                logger.debug("Ticket resolved: %s -> %s (%s)",
                             from_anima, ticket.get("to", "?"), message_id)
                return True
        except (json.JSONDecodeError, OSError, KeyError):
            logger.warning("Failed to resolve ticket: %s", ticket_path)
        return False

    @staticmethod
    def has_open_tickets(outbox_root: Path, anima_name: str) -> bool:
        """Check if an Anima has any unresolved outbox tickets.

        Used by _is_heartbeat_idle() to prevent idle skip while
        waiting for replies.
        """
        outbox_dir = outbox_root / anima_name
        if not outbox_dir.exists():
            return False
        for fp in outbox_dir.glob("*.ticket.json"):
            try:
                ticket = json.loads(fp.read_text(encoding="utf-8"))
                if ticket.get("status") == STATUS_PENDING:
                    return True
            except (json.JSONDecodeError, OSError):
                continue
        return False

    # ── Monitoring loop ───────────────────────────────────

    async def _monitor_loop(self) -> None:
        """Main monitoring loop: check all outboxes for timeouts."""
        while not self._shutdown.is_set():
            try:
                await self._check_all_outboxes()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Ticket manager error")

            try:
                await asyncio.wait_for(
                    self._shutdown.wait(), timeout=_POLL_INTERVAL_SEC,
                )
                break  # shutdown was set
            except asyncio.TimeoutError:
                pass  # normal: continue polling

    async def _check_all_outboxes(self) -> None:
        """Scan all Anima outboxes for timed-out tickets."""
        if not self._outbox_root.exists():
            return

        now = time.time()
        alerts: list[dict[str, Any]] = []

        for anima_dir in sorted(self._outbox_root.iterdir()):
            if not anima_dir.is_dir():
                continue
            anima_name = anima_dir.name

            for fp in anima_dir.glob("*.ticket.json"):
                try:
                    ticket = json.loads(fp.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    continue

                status = ticket.get("status", "")
                created_at = ticket.get("created_at", 0)

                # Timeout: not picked up within _PICKUP_TIMEOUT_SEC
                if status == STATUS_PENDING:
                    elapsed = now - created_at
                    if elapsed > _PICKUP_TIMEOUT_SEC:
                        alerts.append({
                            "type": "pickup_timeout",
                            "from": anima_name,
                            "to": ticket.get("to", "?"),
                            "message_id": ticket.get("message_id", "?"),
                            "elapsed_min": round(elapsed / 60, 1),
                            "preview": ticket.get("content_preview", "")[:100],
                        })
                        # Update status to prevent repeated alerts
                        ticket["status"] = STATUS_TIMEOUT
                        fp.write_text(
                            json.dumps(ticket, ensure_ascii=False, indent=2),
                            encoding="utf-8",
                        )

                # Cleanup: resolved tickets older than 1 hour
                elif status == STATUS_RESOLVED:
                    resolved_at = ticket.get("resolved_at", 0)
                    if resolved_at and (now - resolved_at) > 3600:
                        fp.unlink(missing_ok=True)

                # Cleanup: timed-out tickets older than 2 hours
                elif status == STATUS_TIMEOUT:
                    if (now - created_at) > 7200:
                        fp.unlink(missing_ok=True)

        # Send alerts
        for alert in alerts:
            await self._send_alert(alert)

    async def _send_alert(self, alert: dict[str, Any]) -> None:
        """Send a Telegram notification for a timed-out ticket."""
        try:
            from core.config.models import load_config
            from core.notification.notifier import HumanNotifier

            config = load_config()
            notifier = HumanNotifier.from_config(config.human_notification)
            if not notifier.channel_count:
                logger.warning("Ticket alert: no notification channels configured")
                return

            subject = f"⚠️ メッセージ未引取: {alert['from']} → {alert['to']}"
            body = (
                f"{alert['from']} が {alert['to']} に送ったメッセージが "
                f"{alert['elapsed_min']}分間引き取られていません。\n\n"
                f"内容: {alert['preview']}"
            )

            await notifier.notify(subject, body, priority="high")
            logger.info(
                "Ticket alert sent: %s %s->%s (%s)",
                alert["type"], alert["from"], alert["to"], alert["message_id"],
            )
        except Exception:
            logger.warning("Failed to send ticket alert", exc_info=True)
