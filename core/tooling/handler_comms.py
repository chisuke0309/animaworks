from __future__ import annotations
# AnimaWorks - Digital Anima Framework
# Copyright (C) 2026 AnimaWorks Authors
# SPDX-License-Identifier: Apache-2.0

"""CommsToolsMixin — messaging, channel, DM history, and human notification handlers."""

import json as _json
import logging
import re
from typing import TYPE_CHECKING, Any

from core.i18n import t
from core.time_utils import now_iso

from core.tooling.handler_base import (
    OnMessageSentFn,
    _error_result,
    active_session_type,
    suppress_board_fanout,
)

if TYPE_CHECKING:
    from core.memory.activity import ActivityLogger
    from core.messenger import Messenger
    from core.notification.notifier import HumanNotifier

logger = logging.getLogger("animaworks.tool_handler")


class CommsToolsMixin:
    """Message sending, channel posting/reading, DM history, and human notification."""

    # Declared for type-checker visibility
    _messenger: Messenger | None
    _anima_name: str
    _anima_dir: Any
    _activity: ActivityLogger
    _on_message_sent: OnMessageSentFn | None
    _replied_to: dict[str, set[str]]
    _posted_channels: dict[str, set[str]]
    _human_notifier: HumanNotifier | None
    _pending_notifications: list[dict[str, Any]]
    _session_origin: str
    _session_origin_chain: list[str]
    _my_supervisor: str | None

    def _handle_send_message(self, args: dict[str, Any]) -> str:
        if not self._messenger:
            return "Error: messenger not configured"

        to = args["to"]
        content = args["content"]
        intent = args.get("intent", "")

        # ── Prompt injection detection on message content ──
        from core.execution._sanitize import detect_injection
        injection_findings = detect_injection(content)
        if injection_findings:
            labels = [f["pattern"] for f in injection_findings]
            logger.warning(
                "Prompt injection patterns in send_message "
                "(%s -> %s): %s",
                self._anima_name, to, ", ".join(labels),
            )
            self._activity.log(
                "security_warning",
                tool="send_message",
                summary=f"Injection patterns detected: {', '.join(labels)}",
                meta={
                    "from": self._anima_name,
                    "to": to,
                    "patterns": [f for f in injection_findings],
                },
            )

        # ── Per-run DM limits ──
        if intent not in ("report", "delegation", "question"):
            return t("handler.dm_intent_error")

        current_replied = self.replied_to_for(active_session_type.get())
        if to in current_replied:
            return t("handler.dm_already_sent", to=to)

        if len(current_replied) >= 2 and to not in current_replied:
            return t("handler.dm_max_recipients")

        # ── Cross-session dedup (prevents heartbeat re-sending what inbox already sent) ──
        try:
            _recent_sends = self._activity.recent(
                days=1, limit=20, types=["message_sent"],
            )
            from core.time_utils import now_jst as _now_jst
            from datetime import timedelta as _td
            _cutoff = _now_jst() - _td(minutes=30)
            for _entry in _recent_sends:
                _meta = _entry.meta or {}
                if (
                    _meta.get("to") == to
                    and _meta.get("intent") == intent
                    and _entry.ts >= _cutoff.isoformat()
                ):
                    logger.info(
                        "Cross-session dedup: blocking send_message %s->%s "
                        "(intent=%s, already sent at %s)",
                        self._anima_name, to, intent, _entry.ts,
                    )
                    return (
                        f"Error: 過去30分以内に同じ相手({to})に同じ intent({intent})の"
                        f"メッセージを送信済みです。重複送信を防止しました。"
                    )
        except Exception:
            logger.debug("Cross-session dedup check failed", exc_info=True)

        # ── Resolve recipient ──
        try:
            from core.outbound import resolve_recipient, send_external
            from core.config.models import load_config
            from core.paths import get_animas_dir

            config = load_config()
            animas_dir = get_animas_dir()
            known_animas = {
                d.name for d in animas_dir.iterdir() if d.is_dir()
            } if animas_dir.exists() else set()

            resolved = resolve_recipient(
                to, known_animas, config.external_messaging,
            )

            # ── Command chain enforcement ──
            # Animas with a supervisor may only send to that supervisor (internal).
            # External recipients (Telegram, Slack, etc.) are always allowed.
            supervisor = getattr(self, "_my_supervisor", None)
            if (
                supervisor is not None
                and to in known_animas
                and to != supervisor
            ):
                return _error_result(
                    "CommandChainViolation",
                    f"{self._anima_name} は supervisor の {supervisor} にのみ"
                    f" send_message を送信できます。{to} への直接送信は禁止されています。",
                    suggestion=f"send_message(to='{supervisor}', ...) を使用してください。",
                )

        except (ValueError, Exception) as e:
            from core.exceptions import RecipientNotFoundError
            if isinstance(e, (ValueError, RecipientNotFoundError)):
                session = active_session_type.get()
                if session == "chat":
                    return (
                        f"宛先 '{to}' には send_message で送信できません。"
                        "チャット中は直接テキストで返答すれば人間ユーザーに届きます。"
                        "send_message は他のAnima宛てにのみ使用してください。"
                    )
                return (
                    f"宛先 '{to}' には send_message で送信できません。"
                    "人間への連絡は call_human を使用してください。"
                    "send_message は他のAnima宛てにのみ使用してください。"
                )
            logger.warning(
                "Recipient resolution failed for '%s': %s",
                to, e, exc_info=True,
            )
            return _error_result(
                "RecipientResolutionError",
                f"Failed to resolve recipient '{to}': {e}",
                suggestion="Check config.json external_messaging settings",
            )

        # ── Build outgoing origin_chain (provenance Phase 3) ──
        from core.execution._sanitize import ORIGIN_ANIMA, MAX_ORIGIN_CHAIN_LENGTH
        outgoing_chain = list(self._session_origin_chain)
        if self._session_origin and self._session_origin not in outgoing_chain:
            outgoing_chain.append(self._session_origin)
        if ORIGIN_ANIMA not in outgoing_chain:
            outgoing_chain.append(ORIGIN_ANIMA)
        outgoing_chain = outgoing_chain[:MAX_ORIGIN_CHAIN_LENGTH]

        # ── External routing ──
        if resolved is not None and not resolved.is_internal:
            logger.info(
                "send_message routed externally: to=%s channel=%s",
                to, resolved.channel,
            )
            self._replied_to.setdefault(active_session_type.get(), set()).add(to)
            self._persist_replied_to(to, success=True)

            msg = self._messenger.send(
                to=to,
                content=content,
                thread_id=args.get("thread_id", ""),
                reply_to=args.get("reply_to", ""),
                intent=intent,
                origin_chain=outgoing_chain,
            )

            if self._on_message_sent:
                try:
                    self._on_message_sent(
                        self._messenger.anima_name, to, content,
                    )
                except Exception:
                    logger.exception("on_message_sent callback failed")

            from core.outbound import send_external
            result = send_external(
                resolved, content, sender_name=self._anima_name,
            )
            return result

        # ── Resolve current task_id for message linkage ──
        current_task_id = ""
        try:
            from core.memory.task_queue import TaskQueueManager
            tqm = TaskQueueManager(self._anima_dir)
            active = [
                t for t in tqm.list_tasks()
                if t.status in ("in_progress", "pending")
            ]
            if active:
                # Prefer in_progress; fall back to most recent pending
                in_prog = [t for t in active if t.status == "in_progress"]
                current_task_id = (in_prog or active)[0].task_id
        except (OSError, IndexError, KeyError):
            pass

        # ── Internal messaging ──
        internal_to = resolved.name if resolved else to

        # ── Auto-create task when delegating without an active task_id ──
        # When send_message(intent=delegation) is used instead of delegate_task,
        # no task_queue entry exists. Create one in the target's queue so the
        # delegation chain is trackable in the task management UI.
        if intent == "delegation" and not current_task_id and (resolved is None or resolved.is_internal):
            try:
                from core.memory.task_queue import TaskQueueManager
                from core.paths import get_animas_dir
                target_dir = get_animas_dir() / internal_to
                if target_dir.exists():
                    target_tqm = TaskQueueManager(target_dir)
                    auto_summary = content.split("\n")[0][:100]
                    auto_entry = target_tqm.add_task(
                        source="anima",
                        original_instruction=content,
                        assignee=internal_to,
                        summary=auto_summary,
                        deadline="24h",
                        relay_chain=[self._anima_name],
                    )
                    current_task_id = auto_entry.task_id
                    logger.info(
                        "send_message: auto-created task %s for delegation %s->%s",
                        current_task_id[:8], self._anima_name, internal_to,
                    )
            except Exception:
                logger.debug("send_message: failed to auto-create delegation task", exc_info=True)
        msg = self._messenger.send(
            to=internal_to,
            content=content,
            thread_id=args.get("thread_id", ""),
            reply_to=args.get("reply_to", ""),
            intent=intent,
            task_id=current_task_id,
            pipeline_id=getattr(self, "_current_pipeline_id", ""),
            origin_chain=outgoing_chain,
        )

        if msg.type == "error":
            return f"Error: {msg.content}"

        logger.info("send_message to=%s thread=%s", internal_to, msg.thread_id)
        self._replied_to.setdefault(active_session_type.get(), set()).add(internal_to)
        self._persist_replied_to(internal_to, success=True)

        if self._on_message_sent:
            try:
                self._on_message_sent(
                    self._messenger.anima_name, internal_to, content,
                )
            except Exception:
                logger.exception("on_message_sent callback failed")

        return f"Message sent to {internal_to} (id: {msg.id}, thread: {msg.thread_id})"

    # ── Channel tool handlers ────────────────────────────────

    def _handle_post_channel(self, args: dict[str, Any]) -> str:
        if not self._messenger:
            return "Error: messenger not configured"
        channel = args.get("channel", "")
        text = args.get("text", "")
        if not channel or not text:
            return _error_result("InvalidArguments", "channel and text are required")

        current_posted = self.posted_channels_for(active_session_type.get())
        if channel in current_posted:
            alt_channels = {"general", "ops"} - {channel} - current_posted
            alt_hint = ""
            if alt_channels:
                alt_hint = t(
                    "handler.post_alt_hint",
                    channels=", ".join(f"#{c}" for c in sorted(alt_channels)),
                )
            return t(
                "handler.post_already_posted",
                channel=channel,
                alt_hint=alt_hint,
            )

        # ── Cross-run guard: file-based cooldown check ──
        try:
            from core.config.models import load_config
            cooldown = load_config().heartbeat.channel_post_cooldown_s
        except Exception:
            cooldown = 300
        if cooldown > 0:
            last = self._messenger.last_post_by(self._anima_name, channel)
            if last:
                from datetime import datetime
                from core.time_utils import ensure_aware, now_jst
                try:
                    ts = ensure_aware(datetime.fromisoformat(last["ts"]))
                    elapsed = (now_jst() - ts).total_seconds()
                    if elapsed < cooldown:
                        return t(
                            "handler.post_cooldown",
                            channel=channel,
                            ts=last["ts"][11:16],
                            elapsed=int(elapsed),
                            cooldown=cooldown,
                        )
                except (ValueError, TypeError):
                    pass

        self._messenger.post_channel(channel, text)
        self._posted_channels.setdefault(active_session_type.get(), set()).add(channel)
        logger.info("post_channel channel=%s anima=%s", channel, self._anima_name)

        if not suppress_board_fanout.get():
            self._fanout_board_mentions(channel, text)
        else:
            logger.info(
                "Suppressed board fanout for board_mention reply: channel=%s anima=%s",
                channel, self._anima_name,
            )

        return f"Posted to #{channel}"

    def _fanout_board_mentions(self, channel: str, text: str) -> None:
        """Send DM notifications to mentioned Animas when posting to a board channel."""
        if not self._messenger:
            return

        mentions = re.findall(r"@(\w+)", text)
        if not mentions:
            return

        is_all = "all" in mentions

        from core.paths import get_data_dir
        sockets_dir = get_data_dir() / "run" / "sockets"
        if sockets_dir.exists():
            running = {p.stem for p in sockets_dir.glob("*.sock")}
        else:
            running = set()

        if is_all:
            targets = running - {self._anima_name}
        else:
            named = {m for m in mentions if m != "all"}
            targets = (named & running) - {self._anima_name}

        if not targets:
            return

        from_name = self._anima_name
        fanout_content = (
            f"[board_reply:channel={channel},from={from_name}]\n"
            + t("handler.board_mention_content", from_name=from_name, channel=channel, text=text)
        )

        for target in sorted(targets):
            try:
                self._messenger.send(
                    to=target,
                    content=fanout_content,
                    msg_type="board_mention",
                )
                logger.info(
                    "board_mention fanout: %s -> %s (channel=%s)",
                    from_name, target, channel,
                )
            except Exception:
                logger.warning(
                    "Failed to fanout board_mention to %s", target, exc_info=True,
                )

    def _handle_read_channel(self, args: dict[str, Any]) -> str:
        if not self._messenger:
            return "Error: messenger not configured"
        channel = args.get("channel", "")
        if not channel:
            return _error_result("InvalidArguments", "channel is required")
        limit = args.get("limit", 20)
        human_only = args.get("human_only", False)
        messages = self._messenger.read_channel(channel, limit=limit, human_only=human_only)
        if not messages:
            return f"No messages in #{channel}"
        return _json.dumps(messages, ensure_ascii=False, indent=2)

    def _handle_read_dm_history(self, args: dict[str, Any]) -> str:
        if not self._messenger:
            return "Error: messenger not configured"
        peer = args.get("peer", "")
        if not peer:
            return _error_result("InvalidArguments", "peer is required")
        limit = args.get("limit", 20)
        messages = self._messenger.read_dm_history(peer, limit=limit)
        if not messages:
            return f"No DM history with {peer}"
        return _json.dumps(messages, ensure_ascii=False, indent=2)

    # ── Human notification handler ────────────────────────────

    def _handle_call_human(self, args: dict[str, Any]) -> str:
        if not self._human_notifier:
            return _error_result(
                "NotConfigured",
                "Human notification is not configured",
                suggestion="Enable human_notification in config.json",
            )
        if self._human_notifier.channel_count == 0:
            return _error_result(
                "NotConfigured",
                "No notification channels configured",
                suggestion="Add channels to human_notification.channels in config.json",
            )

        import asyncio

        subject = args.get("subject", "")
        body = args.get("body", "")
        priority = args.get("priority", "normal")

        if not subject or not body:
            return _error_result(
                "InvalidArguments",
                "subject and body are required",
            )

        try:
            coro = self._human_notifier.notify(
                subject, body, priority,
                anima_name=self._anima_name,
            )
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop is not None:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    results = pool.submit(asyncio.run, coro).result(timeout=60)
            else:
                results = asyncio.run(coro)
        except Exception as e:
            return _error_result("NotificationError", f"Failed to send notification: {e}")

        notif_data = {
            "anima": self._anima_name,
            "subject": subject,
            "body": body,
            "priority": priority,
            "timestamp": now_iso(),
        }
        self._pending_notifications.append(notif_data)

        return _json.dumps(
            {"status": "sent", "results": results},
            ensure_ascii=False,
        )
