from __future__ import annotations
# AnimaWorks - Digital Anima Framework
# Copyright (C) 2026 AnimaWorks Authors
# SPDX-License-Identifier: Apache-2.0

"""HeartbeatMixin -- heartbeat/cron prompt construction and cycle execution.

Extracted from ``core.anima.DigitalAnima`` as a Mixin.  All ``self``
references are resolved at runtime via MRO when mixed into ``DigitalAnima``.
"""

import json
import logging
import re
from typing import Any

from core.time_utils import now_iso, now_jst

from core.memory.conversation import ConversationMemory
from core.memory.streaming_journal import StreamingJournal
from core.messenger import InboxItem
from core.paths import load_prompt, get_shared_dir
from core.i18n import t
from core.schemas import CycleResult

logger = logging.getLogger("animaworks.anima")

# ── Reflection extraction ─────────────────────────────────────

_RE_REFLECTION = re.compile(
    r"\[REFLECTION\]\s*\n?(.*?)\n?\s*\[/REFLECTION\]",
    re.DOTALL,
)

_RE_CONTRACT = re.compile(
    r"\[CONTRACT\]\s*\n?(.*?)\n?\s*\[/CONTRACT\]",
    re.DOTALL,
)

_MIN_REFLECTION_LENGTH = 50
_MIN_CONTRACT_LENGTH = 8

# ── Feedback-loop sanitizer for heartbeat output ────────────
#
# The cicchi 5-stage template produces ``## Observe / Plan / Execute /
# Verify / Reflect`` (optionally ``+ Contract``) section headers. LLMs also
# routinely emit variants like ``### Observe``, ``## 🔎 Observe``, ``## ✅
# Plan（計画）`` etc. If any of these slip into heartbeat_end summaries or
# episode entries they re-enter the next prompt via RAG / heartbeat_history
# and the model starts mimicking its own scaffold indefinitely (MEMORY.md).
#
# The pattern below matches any markdown heading (``#`` up to ``####``,
# optionally followed by emoji / CJK punctuation / spaces) where one of the
# six phase names appears on the same line, and deletes that heading plus
# all subsequent content. It is deliberately broader than strict
# ``## Observe`` to tolerate model drift.
_RE_HB_PHASE_HEADER = re.compile(
    r"""
    ^\s*\#{1,4}\s*[^\n]*?            # any heading up to h4 + arbitrary prefix
    (?:Observe|Plan|Execute|Verify|Reflect|Contract)
    \b.*                             # everything after the header
    """,
    re.DOTALL | re.IGNORECASE | re.MULTILINE | re.VERBOSE,
)

# Fallback heading patterns without the Markdown ``#``, e.g. bold-only
# headings like ``**Observe（観察）**`` that Anthropic models sometimes emit.
_RE_HB_BOLD_PHASE = re.compile(
    r"^\s*\*\*\s*(?:Observe|Plan|Execute|Verify|Reflect|Contract)\b.*",
    re.DOTALL | re.IGNORECASE | re.MULTILINE,
)


def _sanitize_hb_summary(raw: str, *, max_len: int = 500) -> str:
    """Strip multi-stage heartbeat scaffolding from a summary string.

    Returns a length-bounded summary safe to persist into activity_log /
    episodes without risking the fenced feedback loop. If everything is
    stripped, returns ``"HEARTBEAT_OK"``.
    """
    if not raw:
        return ""
    if "HEARTBEAT_OK" in raw:
        return "HEARTBEAT_OK"
    stripped = _RE_HB_PHASE_HEADER.sub("", raw)
    stripped = _RE_HB_BOLD_PHASE.sub("", stripped)
    stripped = stripped.strip()
    if not stripped:
        return "HEARTBEAT_OK"
    return stripped[:max_len]


def _extract_reflection(text: str) -> str:
    """Extract [REFLECTION]...[/REFLECTION] block from heartbeat output.

    Returns empty string if not found or content is trivial.
    """
    if not text:
        return ""
    m = _RE_REFLECTION.search(text)
    if m:
        return m.group(1).strip()
    return ""


_CONTRACT_PLACEHOLDER_MARKERS = (
    "（明日の自分",
    "明日の自分への1つの具体的改善",
    "動詞で終える単文",
    "例: ",
    "例：",
)


def _extract_contract(text: str) -> str:
    """Extract [CONTRACT]...[/CONTRACT] block (明日への約束).

    Used by cicchi's 5-stage heartbeat template. Persisted separately in
    activity_log (type: heartbeat_contract) so it can be re-injected into
    the next day's heartbeat without going through the episode feedback
    loop.

    Hardening (Codex review m1):
    - When multiple blocks exist, prefer the LAST non-empty one. LLMs
      sometimes repeat the template example verbatim before writing the
      real contract, so the latter is more likely to be intentional.
    - Reject blocks whose content still contains the template placeholder
      markers; return empty string so the caller does NOT store a bogus
      contract.
    """
    if not text:
        return ""
    matches = list(_RE_CONTRACT.finditer(text))
    for m in reversed(matches):
        candidate = m.group(1).strip()
        if not candidate:
            continue
        if any(marker in candidate for marker in _CONTRACT_PLACEHOLDER_MARKERS):
            continue
        return candidate
    return ""


class HeartbeatMixin:
    """Mixin: heartbeat/cron prompt building, cycle execution, failure handling."""

    # ── Heartbeat history ────────────────────────────────────

    _HEARTBEAT_HISTORY_N = 3

    def _load_heartbeat_history(self) -> str:
        """Load last N heartbeat history entries from unified activity log.

        Falls back to legacy ``shortterm/heartbeat_history/`` when the
        activity log is empty (migration period).
        """
        try:
            entries = self._activity.recent(
                days=2,
                types=["heartbeat_end"],
                limit=self._HEARTBEAT_HISTORY_N,
            )
            if entries:
                lines: list[str] = []
                for e in entries:
                    ts_short = e.ts[11:19] if len(e.ts) >= 19 else e.ts
                    summary = e.summary or e.content
                    lines.append(f"- {ts_short}: {summary}")
                return "\n".join(lines)

            # Legacy fallback: read from shortterm/heartbeat_history/
            legacy = self.memory.load_recent_heartbeat_summary(
                limit=self._HEARTBEAT_HISTORY_N,
            )
            if legacy:
                return legacy
            return ""
        except Exception:
            logger.exception("[%s] Failed to load heartbeat history", self.name)
            return ""

    # ── Heartbeat reflections ─────────────────────────────────

    _RECENT_REFLECTIONS_N = 3

    def _load_recent_reflections(self) -> str:
        """Load recent heartbeat reflections from unified activity log."""
        try:
            entries = self._activity.recent(
                days=3,
                types=["heartbeat_reflection"],
                limit=self._RECENT_REFLECTIONS_N,
            )
            if not entries:
                return ""
            lines: list[str] = []
            for e in entries:
                ts_short = e.ts[11:19] if len(e.ts) >= 19 else e.ts
                content = e.content or e.summary
                lines.append(f"- {ts_short}: {content[:300]}")
            return "\n".join(lines)
        except Exception:
            logger.debug(
                "[%s] Failed to load recent reflections",
                self.name, exc_info=True,
            )
            return ""

    # ── Blackboard (shared/blackboard/*.md) ───────────────────
    #
    # Caps are in UTF-8 bytes, not characters, to keep Japanese content from
    # exploding the prompt (Codex review m3). Rough guide: 8 KB ≈ 2,700 JP
    # chars, 32 KB ≈ 10,000 JP chars.
    _BLACKBOARD_PER_FILE_CAP_BYTES = 8 * 1024
    _BLACKBOARD_TOTAL_CAP_BYTES = 32 * 1024

    @staticmethod
    def _truncate_utf8(body: str, max_bytes: int) -> str:
        """Truncate ``body`` so its UTF-8 encoding fits in ``max_bytes``.

        Rounds down on any multi-byte character boundary so the output
        remains valid UTF-8. Appends a short marker if truncation occurred.
        """
        encoded = body.encode("utf-8")
        if len(encoded) <= max_bytes:
            return body
        # Decode with errors='ignore' to drop any dangling multi-byte seq.
        truncated = encoded[:max_bytes].decode("utf-8", errors="ignore")
        return truncated + "\n\n…(truncated)"

    def _load_blackboard_snapshot(self) -> str:
        """Read all blackboard files and return a single merged body.

        Each file is capped at 8 KB UTF-8; total output capped at 32 KB
        UTF-8. Files are sorted by filename (ascending) for deterministic
        ordering. Missing directory, read errors, and oversized files
        degrade gracefully to empty string / truncated content with a
        warning log.
        """
        try:
            bb_dir = get_shared_dir() / "blackboard"
            if not bb_dir.is_dir():
                return ""
            paths = sorted(p for p in bb_dir.iterdir() if p.is_file() and p.suffix == ".md")
            if not paths:
                return ""
            sections: list[str] = []
            total_bytes = 0
            for p in paths:
                try:
                    body = p.read_text(encoding="utf-8")
                except Exception:
                    logger.debug("[%s] Blackboard read failed: %s", self.name, p, exc_info=True)
                    continue
                body = self._truncate_utf8(body, self._BLACKBOARD_PER_FILE_CAP_BYTES)
                section = f"### {p.name}\n\n{body.rstrip()}"
                section_bytes = len(section.encode("utf-8"))
                if total_bytes + section_bytes > self._BLACKBOARD_TOTAL_CAP_BYTES:
                    logger.warning(
                        "[%s] Blackboard total cap reached; truncating at %s",
                        self.name, p.name,
                    )
                    break
                sections.append(section)
                total_bytes += section_bytes
            return "\n\n".join(sections)
        except Exception:
            logger.debug("[%s] Failed to load blackboard", self.name, exc_info=True)
            return ""

    # ── Heartbeat private methods ──────────────────────────

    def _build_prior_messages(
        self, prompt_text: str,
    ) -> list[dict[str, Any]] | None:
        """Build prior_messages for A mode, None for S/B."""
        mode = self.agent.execution_mode
        if mode != "a":
            return None
        conv = ConversationMemory(self.anima_dir, self.model_config)
        return conv.build_structured_messages(prompt_text)

    def _build_background_context_parts(self) -> list[str]:
        """Build shared context parts for background-auto sessions (heartbeat/cron).

        Collects: recovery note, background task notifications, heartbeat
        history, reflections, dialogue context, subordinate check.
        """
        parts: list[str] = []

        # ── Recovery note from previous failed heartbeat ──
        recovery_note_path = self.anima_dir / "state" / "recovery_note.md"
        if recovery_note_path.exists():
            try:
                recovery_content = recovery_note_path.read_text(encoding="utf-8")
                parts.append(
                    load_prompt("fragments/recovery_note_header") + "\n\n" + recovery_content
                )
                recovery_note_path.unlink(missing_ok=True)
                logger.info("[%s] Recovery note loaded and removed", self.name)
            except Exception:
                logger.debug("[%s] Failed to read recovery note", self.name, exc_info=True)

        # ── Blackboard snapshot (organization-wide shared state) ──
        blackboard_body = self._load_blackboard_snapshot()
        if blackboard_body:
            try:
                header = load_prompt("fragments/blackboard_header")
            except Exception:
                logger.debug(
                    "[%s] blackboard_header fragment missing; using default",
                    self.name, exc_info=True,
                )
                header = "# 共有ブラックボード（Organization-Wide State）"
            parts.append(header + "\n\n" + blackboard_body)

        # Inject pending background task notifications
        bg_notifications = self.drain_background_notifications()
        if bg_notifications:
            notif_text = "\n\n".join(bg_notifications)
            parts.append(
                load_prompt("fragments/bg_task_notification") + "\n\n" + notif_text
            )

        # Inject recent heartbeat history for continuity
        history_text = self._load_heartbeat_history()
        if history_text:
            parts.append(load_prompt(
                "heartbeat_history", history=history_text,
            ))

        # Inject recent reflections for cognitive continuity
        reflection_text = self._load_recent_reflections()
        if reflection_text:
            parts.append(
                load_prompt("fragments/recent_reflections") + "\n\n" + reflection_text
            )

        # Inject recent dialogue context for cross-session continuity
        try:
            conv_mem = ConversationMemory(self.anima_dir, self.model_config)
            state = conv_mem.load()
            recent_turns = state.turns[-5:] if state.turns else []
            if recent_turns:
                conv_lines = []
                for turn in recent_turns:
                    snippet = turn.content[:200]
                    conv_lines.append(f"- [{turn.role}] {snippet}")
                conv_summary = "\n".join(conv_lines)
                parts.append(
                    t("agent.recent_dialogue_header") + "\n\n"
                    + t("agent.recent_dialogue_intro")
                    + "\n"
                    + t("agent.recent_dialogue_consider") + "\n\n"
                    + conv_summary
                )
        except Exception:
            logger.debug("[%s] Failed to load dialogue context", self.name, exc_info=True)

        # ── Subordinate management check for animas with subordinates ──
        try:
            from core.config.models import load_config
            from core.paths import get_animas_dir
            _cfg = load_config()
            _subordinates = [
                _name for _name, _pcfg in _cfg.animas.items()
                if _pcfg.supervisor == self.name
            ]
            if _subordinates:
                parts.append(load_prompt(
                    "heartbeat_subordinate_check",
                    subordinates=", ".join(_subordinates),
                    animas_dir=str(get_animas_dir()),
                ))
        except Exception:
            logger.debug(
                "[%s] Failed to inject delegation check", self.name,
                exc_info=True,
            )

        return parts

    def _handle_stale_task_auto_blocking(self) -> str:
        """Auto-block long-stale tasks and reset current_task.md if needed.

        Calls TaskQueueManager.auto_block_stale_tasks() and, if any tasks were
        blocked, resets current_task.md to idle so the next LLM cycle won't be
        paralysed by a stale stuck-state.

        Returns a notification fragment for prompt injection, or "" if nothing
        was blocked.
        """
        try:
            from core.memory.task_queue import TaskQueueManager
            tq = TaskQueueManager(self.anima_dir)

            notification = ""

            # ── Task queue maintenance (mandatory on every execution path) ──
            # Heartbeat / Inbox / Cron すべての実行パスで 3関数をセットで実行する。
            # 詳細は AGENTS.md「タスクキュー保守契約」参照。
            # Phase 1: Auto-block tasks stale for 2+ hours
            blocked = tq.auto_block_stale_tasks()
            if blocked:
                items = "\n".join(
                    f"  - [{task.task_id[:8]}] {task.summary[:100]}"
                    for task in blocked
                )

                # Reset current_task.md to idle if it's not already
                current_state = self.memory.read_current_state()
                if "status: idle" not in current_state.lower():
                    ts = now_jst().strftime("%Y-%m-%d %H:%M")
                    self.memory.update_state(
                        f"status: idle\n\n"
                        f"---\n\n"
                        f"⚠️ {ts}: 以下のタスクを自動blocked化しました（2時間更新なし）:\n{items}"
                    )

                self._activity.log(
                    "task_auto_blocked",
                    summary=f"タスク自動blocked: {len(blocked)}件",
                    meta={"blocked_count": len(blocked), "task_ids": [task.task_id for task in blocked]},
                )

                notification = (
                    f"## ⚠️ スタックタスク自動blocked通知\n\n"
                    f"以下の {len(blocked)} 件のタスクが2時間以上更新されていないため、"
                    f"自動的にblocked状態に遷移しました。\n"
                    f"依頼者への報告が必要な場合はsend_messageで連絡してください。\n\n"
                    f"{items}"
                )

            # Phase 2: Auto-resolve tasks stale for 24+ hours
            resolved = tq.auto_resolve_old_tasks()
            if resolved:
                self._activity.log(
                    "task_auto_resolved",
                    summary=f"タスク自動完了: {len(resolved)}件（24時間以上更新なし）",
                    meta={"resolved_count": len(resolved), "task_ids": [t.task_id for t in resolved]},
                )

            # Phase 3: Compact JSONL if it has grown too large
            tq.maybe_compact()

            return notification
        except Exception:
            logger.debug("[%s] Failed to auto-block stale tasks", self.name, exc_info=True)
            return ""

    def _resolve_heartbeat_template_name(self) -> str:
        """Return the heartbeat template name, preferring a per-Anima override.

        Looks for ``heartbeat.<anima_name>.md`` first; falls back to the
        shared ``heartbeat.md``. Makes per-Anima customization opt-in: create
        the file, no code change required.
        """
        per_anima = f"heartbeat.{self.name}"
        try:
            # Probe by loading with no substitutions; cache hit is cheap.
            load_prompt(per_anima)
            return per_anima
        except FileNotFoundError:
            return "heartbeat"
        except Exception:
            logger.debug(
                "[%s] Per-Anima heartbeat template probe failed; using shared",
                self.name, exc_info=True,
            )
            return "heartbeat"

    def _load_latest_contract(self) -> str:
        """Load the Contract (明日への約束) written before today.

        The contract is meant as "a promise from yesterday to today". If
        cicchi runs heartbeat twice in the same day, the earlier run's
        contract is NOT yet due to be treated as "yesterday's"; otherwise
        the afternoon HB would read the morning's contract as if it had
        already passed (Codex review M4).

        We therefore filter by date boundary: return the newest contract
        strictly before today's local (JST) date.

        Pulled from activity_log (not episodes) to avoid the feedback loop.
        ``ActivityLog.recent`` returns chronological (oldest-first) order, so
        we iterate in reverse to find the most recent qualifying entry.
        """
        try:
            today_iso = now_jst().date().isoformat()
            entries = self._activity.recent(
                days=7,
                types=["heartbeat_contract"],
                limit=20,
            )
            for e in reversed(entries):
                # activity_log stores ts in ISO format; take the YYYY-MM-DD
                # prefix for a robust date comparison.
                entry_date = (e.ts or "")[:10]
                if entry_date and entry_date < today_iso:
                    return (e.content or e.summary or "").strip()
            return ""
        except Exception:
            logger.debug(
                "[%s] Failed to load latest contract",
                self.name, exc_info=True,
            )
            return ""

    async def _build_heartbeat_prompt(self) -> list[str]:
        """Build heartbeat prompt parts.

        Heartbeat-specific header + shared background context.
        Auto-blocks long-stale tasks before building the context.
        """
        hb_config = self.memory.read_heartbeat_config()
        checklist = hb_config or load_prompt("heartbeat_default_checklist")
        task_delegation_rules = load_prompt("task_delegation_rules")

        template_name = self._resolve_heartbeat_template_name()

        # Only cicchi's 5-stage template renders the contract block. Other
        # templates ignore the kwarg thanks to SafeFormatDict.
        yesterdays_contract_block = ""
        if template_name != "heartbeat":
            contract = self._load_latest_contract()
            if contract:
                yesterdays_contract_block = (
                    "## 昨日の自分からの約束（Contract）\n\n"
                    f"> {contract}\n\n"
                    "**Planフェーズの冒頭で必ずこの約束を参照し、"
                    "Verifyで遵守度を評価すること。**"
                )

        try:
            header = load_prompt(
                template_name,
                checklist=checklist,
                task_delegation_rules=task_delegation_rules,
                yesterdays_contract_block=yesterdays_contract_block,
            )
        except Exception:
            logger.warning(
                "[%s] Per-Anima template %r failed; falling back to shared heartbeat",
                self.name, template_name, exc_info=True,
            )
            header = load_prompt(
                "heartbeat",
                checklist=checklist,
                task_delegation_rules=task_delegation_rules,
            )
        parts = [header]

        # Auto-block tasks stuck for 2+ hours and notify LLM
        stale_notification = self._handle_stale_task_auto_blocking()
        if stale_notification:
            parts.append(stale_notification)

        parts.extend(self._build_background_context_parts())

        return parts

    def _build_cron_prompt(
        self, task_name: str, description: str, command_output: str | None = None,
    ) -> str:
        """Build cron task prompt with heartbeat-equivalent context.

        Args:
            task_name: Cron task name from cron.md.
            description: Task description or instruction.
            command_output: Optional stdout from a preceding command-type cron.
        """
        parts: list[str] = []

        # Cron task header
        cron_prompt = load_prompt(
            "cron_task", task_name=task_name, description=description,
        )
        if cron_prompt:
            parts.append(cron_prompt)

        # Inject command output if this is a follow-up to a command cron
        if command_output:
            parts.append(load_prompt("fragments/command_output", output=command_output))

        # Shared background context (same as heartbeat)
        parts.extend(self._build_background_context_parts())

        return "\n\n".join(parts)

    async def _execute_heartbeat_cycle(
        self,
        prompt: str,
        inbox_items: list[InboxItem],
        unread_count: int,
        prior_messages: list[dict[str, Any]] | None = None,
    ) -> CycleResult:
        """Write checkpoint, execute agent cycle, record results.

        Args:
            prompt: The heartbeat prompt text.
            inbox_items: Inbox items being processed.
            unread_count: Number of unread messages.
            prior_messages: Structured conversation history for Mode A.

        Returns the CycleResult from the agent execution.
        """
        # ── Heartbeat Checkpoint ──
        checkpoint_path = self.anima_dir / "state" / "heartbeat_checkpoint.json"
        try:
            checkpoint_data = {
                "ts": now_iso(),
                "trigger": "heartbeat",
                "unread_count": unread_count,
            }
            checkpoint_path.write_text(
                json.dumps(checkpoint_data, ensure_ascii=False), encoding="utf-8",
            )
        except Exception:
            logger.debug("[%s] Failed to write heartbeat checkpoint", self.name, exc_info=True)

        # Reset in-memory reply/channel tracking, then reload recent sends
        # from activity_log so heartbeat won't duplicate what inbox already sent.
        self.agent.reset_reply_tracking()
        self.agent.reset_posted_channels()
        _replied_to_path = self.anima_dir / "run" / "replied_to.jsonl"
        if _replied_to_path.exists():
            _replied_to_path.unlink(missing_ok=True)
        # Merge recent message_sent recipients (last 30 min) so per-run
        # dedup guard also blocks duplicates across inbox→heartbeat boundary.
        try:
            from datetime import timedelta as _td
            _cutoff = now_jst() - _td(minutes=30)
            _recent = self._activity.recent(
                days=1, limit=20, types=["message_sent"],
            )
            _recent_to: set[str] = set()
            for _e in _recent:
                if _e.ts >= _cutoff.isoformat():
                    _m = _e.meta or {}
                    if _m.get("to"):
                        _recent_to.add(_m["to"])
            if _recent_to:
                self.agent._tool_handler.merge_replied_to(
                    _recent_to, session_type="heartbeat",
                )
                logger.debug(
                    "[%s] Heartbeat pre-loaded replied_to from activity: %s",
                    self.name, _recent_to,
                )
        except Exception:
            logger.debug(
                "[%s] Failed to pre-load replied_to", self.name, exc_info=True,
            )

        accumulated_text = ""
        result: CycleResult | None = None

        # Streaming journal for heartbeat crash recovery
        journal = StreamingJournal(self.anima_dir, session_type="heartbeat")
        journal.open(trigger="heartbeat")

        # Set session type so sends go into _replied_to["heartbeat"] (not "chat")
        from core.tooling.handler_base import active_session_type as _active_session_type
        _hb_session_token = self.agent._tool_handler.set_active_session_type("heartbeat")

        # pipeline_id: lifecycle側で設定済みの場合はそのまま使う。
        # 未設定の場合のみ新規発番する（後方互換）。
        import uuid as _uuid
        if not getattr(self.agent._tool_handler, "_current_pipeline_id", ""):
            self.agent._tool_handler._current_pipeline_id = _uuid.uuid4().hex[:16]
            # fallback 発番時も ActivityLogger に反映
            try:
                self.agent._tool_handler._activity.current_pipeline_id = (
                    self.agent._tool_handler._current_pipeline_id
                )
            except AttributeError:
                pass

        try:
            async for chunk in self.agent.run_cycle_streaming(
                prompt, trigger="heartbeat",
                prior_messages=prior_messages,
            ):
                # Relay text_delta chunks to waiting user stream
                if chunk.get("type") == "text_delta":
                    accumulated_text += chunk.get("text", "")
                    journal.write_text(chunk.get("text", ""))

                if chunk.get("type") == "cycle_done":
                    cycle_result = chunk.get("cycle_result", {})
                    result = CycleResult(
                        trigger=cycle_result.get("trigger", "heartbeat"),
                        action=cycle_result.get("action", "responded"),
                        summary=cycle_result.get("summary", ""),
                        duration_ms=cycle_result.get("duration_ms", 0),
                        context_usage_ratio=cycle_result.get(
                            "context_usage_ratio", 0.0
                        ),
                        session_chained=cycle_result.get(
                            "session_chained", False
                        ),
                        total_turns=cycle_result.get("total_turns", 0),
                    )
                    journal.finalize(summary=result.summary[:500])

            if result is None:
                result = CycleResult(
                    trigger="heartbeat",
                    action="responded",
                    summary=accumulated_text or "(no result)",
                )

            self._last_activity = now_jst()

            # Activity log: heartbeat end.
            # Strip multi-stage scaffolding before persisting to activity_log
            # AND to episodes (next step). Both paths route to the next HB's
            # prompt (activity_log via heartbeat_history, episodes via RAG),
            # so they must use the same sanitiser.
            _hb_summary = _sanitize_hb_summary(result.summary or "", max_len=200)
            self._activity.log("heartbeat_end", summary=_hb_summary)

            # Session boundary: finalize pending conversation turns
            try:
                conv_mem = ConversationMemory(self.anima_dir, self.model_config)
                await conv_mem.finalize_if_session_ended()
            except Exception:
                logger.debug("[%s] finalize_if_session_ended failed", self.name, exc_info=True)

            # A-3: Record important heartbeat actions to episodes.
            # Same sanitiser as heartbeat_end — episodes feed RAG which feeds
            # the next prompt, so verbose scaffolding must NOT leak here
            # either. ``_hb_summary`` (already sanitised at max_len=200) is a
            # no-op if it collapsed to HEARTBEAT_OK.
            _episode_summary = _sanitize_hb_summary(result.summary or "", max_len=500)
            if _episode_summary and _episode_summary != "HEARTBEAT_OK":
                ts = now_jst().strftime("%H:%M")
                episode_entry = t(
                    "anima.heartbeat_episode",
                    ts=ts,
                    summary=_episode_summary,
                )
                if unread_count > 0:
                    episode_entry += t("anima.heartbeat_msgs_processed", count=unread_count)

                # A-3b: Extract and record reflection from accumulated text
                # Reflections are only saved when the heartbeat actually took action
                # (_hb_summary != HEARTBEAT_OK). This ensures O/P/R artifacts from
                # verbose no-op runs are never persisted into the feedback loop.
                reflection_text = _extract_reflection(accumulated_text)
                if reflection_text and len(reflection_text) >= _MIN_REFLECTION_LENGTH and _hb_summary != "HEARTBEAT_OK":
                    episode_entry += (
                        f"\n\n[REFLECTION]\n{reflection_text}\n[/REFLECTION]"
                    )
                    self._activity.log(
                        "heartbeat_reflection",
                        content=reflection_text,
                        summary=reflection_text[:200],
                    )

                # A-3c: Extract and record Contract (明日への約束)
                # Contract is persisted to activity_log only — NOT to episodes —
                # so the next day's heartbeat can re-inject it without going
                # through RAG. This deliberately sidesteps the episode feedback
                # loop documented in MEMORY.md.
                contract_text = _extract_contract(accumulated_text)
                if contract_text and len(contract_text) >= _MIN_CONTRACT_LENGTH and _hb_summary != "HEARTBEAT_OK":
                    self._activity.log(
                        "heartbeat_contract",
                        content=contract_text,
                        summary=contract_text[:200],
                    )

                try:
                    self.memory.append_episode(episode_entry)
                except Exception:
                    logger.debug("[%s] Failed to record heartbeat episode", self.name, exc_info=True)

            logger.info(
                "[%s] run_heartbeat END duration_ms=%d unread_processed=%d",
                self.name, result.duration_ms, unread_count,
            )
            # Heartbeat completed successfully — remove checkpoint
            try:
                checkpoint_path.unlink(missing_ok=True)
            except Exception:
                logger.debug("[%s] Failed to remove heartbeat checkpoint", self.name, exc_info=True)

            return result
        finally:
            journal.close()
            _active_session_type.reset(_hb_session_token)

    async def _handle_heartbeat_failure(
        self,
        error: Exception,
        inbox_items: list[InboxItem],
        unread_count: int,
    ) -> None:
        """Handle heartbeat failure: crash-archive, log error, save recovery note."""
        logger.exception("[%s] run_heartbeat FAILED", self.name)

        # Archive inbox messages even on crash to prevent
        # re-processing storms on next heartbeat.
        if inbox_items:
            try:
                crash_archived = self.messenger.archive_paths(inbox_items)
                logger.info(
                    "[%s] Crash-archived %d/%d inbox messages",
                    self.name, crash_archived, len(inbox_items),
                )
            except Exception:
                logger.warning(
                    "[%s] Failed to crash-archive inbox messages",
                    self.name, exc_info=True,
                )

        # Activity log: error
        self._activity.log(
            "error",
            summary=t("anima.heartbeat_error", exc=type(error).__name__),
            meta={"phase": "run_heartbeat", "error": str(error)[:200]},
        )

        # ── Save recovery note for next heartbeat ──
        try:
            recovery_path = self.anima_dir / "state" / "recovery_note.md"
            recovery_content = t(
                "anima.recovery_error_info",
                exc_type=type(error).__name__,
                exc_msg=str(error)[:200],
                ts=now_iso(),
                count=unread_count,
            )
            recovery_path.write_text(recovery_content, encoding="utf-8")
            logger.info("[%s] Recovery note saved", self.name)
        except Exception:
            logger.debug("[%s] Failed to save recovery note", self.name, exc_info=True)

        # Clean up orphaned streaming journal in-process so that
        # the next restart does not misreport it as a "crash recovery".
        try:
            if StreamingJournal.has_orphan(self.anima_dir, session_type="heartbeat"):
                StreamingJournal.confirm_recovery(self.anima_dir, session_type="heartbeat")
                logger.info("[%s] Cleaned up orphaned streaming journal", self.name)
        except Exception:
            logger.debug(
                "[%s] Failed to clean up streaming journal",
                self.name, exc_info=True,
            )

    # ── run_heartbeat orchestrator ───────────────────────────

    def _trigger_pending_task_execution(self) -> None:
        """Signal PendingTaskExecutor to check for new tasks.

        Called after heartbeat completion to ensure tasks written
        during planning phase are picked up promptly.
        """
        pending_dir = self.anima_dir / "state" / "pending"
        if not pending_dir.exists():
            return
        task_files = list(pending_dir.glob("*.json"))
        if task_files:
            logger.info(
                "[%s] %d pending tasks found after heartbeat, signaling executor",
                self.name, len(task_files),
            )
            if self._pending_executor is not None:
                self._pending_executor.wake()
