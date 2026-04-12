"""
System scheduler mixin for ProcessSupervisor.
"""

# AnimaWorks - Digital Anima Framework
# Copyright (C) 2026 AnimaWorks Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from core.supervisor.process_handle import ProcessState

logger = logging.getLogger(__name__)

_DEFAULT_TIMEZONE = "Asia/Tokyo"


class SchedulerMixin:
    """System-level cron scheduler for memory consolidation and log rotation."""

    def _start_system_scheduler(self) -> None:
        """Start the system-level scheduler for consolidation crons."""
        try:
            self.scheduler = AsyncIOScheduler(timezone=_DEFAULT_TIMEZONE)
            self._setup_system_crons()
            self.scheduler.start()
            self._scheduler_running = True
            logger.info("System scheduler started")
        except Exception:
            logger.exception("Failed to start system scheduler")
            self.scheduler = None
            self._scheduler_running = False

    @staticmethod
    def _load_config_attr(attr: str, context: str) -> Any:
        """Load a top-level config attribute, returning ``None`` on failure."""
        try:
            from core.config import load_config
            return getattr(load_config(), attr, None)
        except Exception:
            logger.debug("Config load failed for %s", context, exc_info=True)
            return None

    @staticmethod
    def _parse_time_spec(time_str: str) -> dict[str, int]:
        """Parse ``HH:MM``, ``day:HH:MM``, or ``dom:HH:MM`` into CronTrigger kwargs.

        Returns a dict with keys like ``hour``, ``minute``, and optionally
        ``day_of_week`` or ``day``.
        """
        parts = time_str.split(":")
        hour, minute = int(parts[-2]), int(parts[-1])
        kwargs: dict[str, int] = {"hour": hour, "minute": minute}
        if len(parts) == 3:
            prefix = parts[0]
            # Numeric prefix → day of month, alpha → day of week
            if prefix.isdigit():
                kwargs["day"] = int(prefix)
            else:
                kwargs["day_of_week"] = prefix  # type: ignore[assignment]
        return kwargs

    def _setup_system_crons(self) -> None:
        """Register system-wide cron jobs for memory consolidation."""
        if not self.scheduler:
            return

        consolidation_cfg = self._load_config_attr("consolidation", "consolidation schedule")

        # ── Consolidation jobs (daily / weekly / monthly) ────────
        _CONSOLIDATION_JOBS: list[tuple[str, str, str, str, Any]] = [
            # (enabled_attr, time_attr, default_time, job_id, callback)
            ("daily_enabled", "daily_time", "02:00",
             "system_daily_consolidation", self._run_daily_consolidation),
            ("weekly_enabled", "weekly_time", "sun:03:00",
             "system_weekly_integration", self._run_weekly_integration),
            ("monthly_enabled", "monthly_time", "1:04:00",
             "system_monthly_forgetting", self._run_monthly_forgetting),
        ]

        for enabled_attr, time_attr, default_time, job_id, callback in _CONSOLIDATION_JOBS:
            enabled = getattr(consolidation_cfg, enabled_attr, True) if consolidation_cfg else True
            time_str = getattr(consolidation_cfg, time_attr, default_time) if consolidation_cfg else default_time
            if not enabled:
                continue
            trigger_kwargs = self._parse_time_spec(time_str)
            self.scheduler.add_job(
                callback,
                CronTrigger(**trigger_kwargs),
                id=job_id,
                name=f"System: {job_id.replace('system_', '').replace('_', ' ').title()}",
                replace_existing=True,
            )
            logger.info("System cron: %s at %s JST", job_id, time_str)

        # ── Task queue stale cleanup ─────────────────────────────
        self.scheduler.add_job(
            self._run_task_queue_cleanup,
            CronTrigger(hour=6, minute=0),
            id="system_task_queue_cleanup",
            name="System: Task Queue Stale Cleanup",
            replace_existing=True,
        )
        logger.info("System cron: task_queue stale cleanup at 06:00 JST")

        # ── Episodes rotation (keep 7 days) ──────────────────────
        self.scheduler.add_job(
            self._run_episodes_rotation,
            CronTrigger(hour=3, minute=30),
            id="system_episodes_rotation",
            name="System: Episodes Rotation",
            replace_existing=True,
        )
        logger.info("System cron: episodes rotation at 03:30 JST")

        # ── Knowledge rotation (keep 7 days) ─────────────────────
        self.scheduler.add_job(
            self._run_knowledge_rotation,
            CronTrigger(hour=3, minute=35),
            id="system_knowledge_rotation",
            name="System: Knowledge Rotation",
            replace_existing=True,
        )
        logger.info("System cron: knowledge rotation at 03:35 JST")

        # ── Engagement log rotation (monthly, keep 30 days) ──────
        self.scheduler.add_job(
            self._run_engagement_log_rotation,
            CronTrigger(day=1, hour=4, minute=0),
            id="system_engagement_log_rotation",
            name="System: Engagement Log Rotation",
            replace_existing=True,
        )
        logger.info("System cron: engagement_log rotation at 1st 04:00 JST")

        # ── Activity log rotation ────────────────────────────────
        try:
            from core.config.models import ActivityLogConfig

            activity_cfg = self._load_config_attr("activity_log", "activity_log rotation schedule")
            if not isinstance(activity_cfg, ActivityLogConfig):
                activity_cfg = ActivityLogConfig()

            if activity_cfg.rotation_enabled:
                r_hour, r_minute = (int(x) for x in activity_cfg.rotation_time.split(":"))
                self.scheduler.add_job(
                    self._run_activity_log_rotation,
                    CronTrigger(hour=r_hour, minute=r_minute),
                    id="system_activity_log_rotation",
                    name="System: Activity Log Rotation",
                    replace_existing=True,
                )
                logger.info("System cron: Activity log rotation at %s JST", activity_cfg.rotation_time)
        except Exception:
            logger.debug("Activity log rotation schedule setup failed", exc_info=True)

    def _iter_consolidation_targets(self) -> list[tuple[str, Path]]:
        """Return (anima_name, anima_dir) for all initialized and enabled animas.

        Scans ``self.animas_dir`` on disk so that stopped / crashed animas are
        still included.  Matches the guard pattern used by ``_reconcile()``.
        """
        if not self.animas_dir.exists():
            return []

        targets: list[tuple[str, Path]] = []
        for anima_dir in sorted(self.animas_dir.iterdir()):
            if not anima_dir.is_dir():
                continue
            if not (anima_dir / "identity.md").exists():
                continue
            if not (anima_dir / "status.json").exists():
                continue
            if not self.read_anima_enabled(anima_dir):
                continue
            targets.append((anima_dir.name, anima_dir))
        return targets

    async def _run_daily_consolidation(self) -> None:
        """Run daily consolidation for all animas via IPC.

        Sends ``run_consolidation`` IPC requests to running Anima processes,
        then performs metadata-based post-processing (synaptic downscaling,
        RAG index rebuild) from the supervisor process.
        """
        logger.info("Starting system-wide daily consolidation")

        from core.config.models import ConsolidationConfig
        consolidation_cfg = self._load_config_attr("consolidation", "daily consolidation")
        default_max = ConsolidationConfig().max_turns
        max_turns = getattr(consolidation_cfg, "max_turns", default_max) if consolidation_cfg else default_max

        for anima_name, anima_dir in self._iter_consolidation_targets():
            handle = self.processes.get(anima_name)
            if not handle or handle.state != ProcessState.RUNNING:
                logger.info(
                    "Daily consolidation skipped for %s: process not running",
                    anima_name,
                )
                continue

            try:
                response = await handle.send_request(
                    "run_consolidation",
                    {"consolidation_type": "daily", "max_turns": max_turns},
                    timeout=600.0,
                )

                if response.error:
                    logger.error(
                        "Daily consolidation IPC error for %s: %s",
                        anima_name, response.error,
                    )
                    continue

                result = response.result or {}
                logger.info(
                    "Daily consolidation for %s: duration_ms=%d",
                    anima_name,
                    result.get("duration_ms", 0),
                )

                # Post-processing: Synaptic downscaling (metadata-based, no LLM)
                try:
                    from core.memory.forgetting import ForgettingEngine
                    forgetter = ForgettingEngine(anima_dir, anima_name)
                    downscaling_result = forgetter.synaptic_downscaling()
                    logger.info(
                        "Synaptic downscaling for %s: %s",
                        anima_name, downscaling_result,
                    )
                except Exception:
                    logger.exception(
                        "Synaptic downscaling failed for anima=%s", anima_name,
                    )

                # Post-processing: Rebuild RAG index
                try:
                    from core.memory.consolidation import ConsolidationEngine
                    engine = ConsolidationEngine(anima_dir, anima_name)
                    engine._rebuild_rag_index()
                except Exception:
                    logger.exception(
                        "RAG index rebuild failed for anima=%s", anima_name,
                    )

                await self._broadcast_event(
                    "system.consolidation",
                    {
                        "anima": anima_name,
                        "type": "daily",
                        "summary": result.get("summary", ""),
                        "duration_ms": result.get("duration_ms", 0),
                    },
                )
            except Exception:
                logger.exception("Daily consolidation failed for %s", anima_name)

    async def _run_weekly_integration(self) -> None:
        """Run weekly integration for all animas via IPC.

        Sends ``run_consolidation`` IPC requests to running Anima processes,
        then performs metadata-based post-processing (neurogenesis reorganization,
        RAG index rebuild) from the supervisor process.
        """
        logger.info("Starting system-wide weekly integration")

        from core.config.models import ConsolidationConfig as _CC
        consolidation_cfg = self._load_config_attr("consolidation", "weekly integration")
        default_max = _CC().max_turns
        max_turns = getattr(consolidation_cfg, "max_turns", default_max) if consolidation_cfg else default_max

        for anima_name, anima_dir in self._iter_consolidation_targets():
            handle = self.processes.get(anima_name)
            if not handle or handle.state != ProcessState.RUNNING:
                logger.info(
                    "Weekly integration skipped for %s: process not running",
                    anima_name,
                )
                continue

            try:
                response = await handle.send_request(
                    "run_consolidation",
                    {"consolidation_type": "weekly", "max_turns": max_turns},
                    timeout=600.0,
                )

                if response.error:
                    logger.error(
                        "Weekly integration IPC error for %s: %s",
                        anima_name, response.error,
                    )
                    continue

                result = response.result or {}
                logger.info(
                    "Weekly integration for %s: duration_ms=%d",
                    anima_name,
                    result.get("duration_ms", 0),
                )

                # Post-processing: Neurogenesis reorganization (metadata-based)
                try:
                    from core.memory.forgetting import ForgettingEngine
                    forgetter = ForgettingEngine(anima_dir, anima_name)
                    reorg_result = forgetter.neurogenesis_reorganize()
                    logger.info(
                        "Neurogenesis reorganization for %s: %s",
                        anima_name, reorg_result,
                    )
                except Exception:
                    logger.exception(
                        "Neurogenesis reorganization failed for anima=%s",
                        anima_name,
                    )

                # Post-processing: Rebuild RAG index
                try:
                    from core.memory.consolidation import ConsolidationEngine
                    engine = ConsolidationEngine(anima_dir, anima_name)
                    engine._rebuild_rag_index()
                except Exception:
                    logger.exception(
                        "RAG index rebuild failed for anima=%s", anima_name,
                    )

                await self._broadcast_event(
                    "system.consolidation",
                    {
                        "anima": anima_name,
                        "type": "weekly",
                        "summary": result.get("summary", ""),
                        "duration_ms": result.get("duration_ms", 0),
                    },
                )
            except Exception:
                logger.exception("Weekly integration failed for %s", anima_name)

    async def _run_monthly_forgetting(self) -> None:
        """Run monthly forgetting for all animas."""
        logger.info("Starting system-wide monthly forgetting")

        for anima_name, anima_dir in self._iter_consolidation_targets():
            try:
                from core.memory.consolidation import ConsolidationEngine

                engine = ConsolidationEngine(
                    anima_dir=anima_dir,
                    anima_name=anima_name,
                )

                result = await engine.monthly_forget()

                logger.info(
                    "Monthly forgetting for %s: forgotten=%d, archived=%d files",
                    anima_name,
                    result.get("forgotten_chunks", 0),
                    len(result.get("archived_files", [])),
                )

                if not result.get("skipped"):
                    await self._broadcast_event(
                        "system.consolidation",
                        {"anima": anima_name, "type": "monthly_forgetting", "result": result},
                    )
            except Exception:
                logger.exception("Monthly forgetting failed for %s", anima_name)

    async def _run_task_queue_cleanup(self) -> None:
        """Mark expired pending/in_progress tasks as 'expired' for all animas.

        Runs daily at 06:00 JST. Targets tasks whose ``deadline`` is in the past
        and whose status is still ``pending`` or ``in_progress``.
        """
        import json
        from datetime import datetime, timezone

        logger.info("Starting system-wide task_queue stale cleanup")
        now = datetime.now(timezone.utc)
        total_expired = 0

        for anima_name, anima_dir in self._iter_consolidation_targets():
            queue_path = anima_dir / "state" / "task_queue.jsonl"
            if not queue_path.exists():
                continue
            try:
                lines = queue_path.read_text(encoding="utf-8").splitlines()
                updated = []
                changed = 0
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    entry = json.loads(line)
                    if entry.get("status") in ("pending", "in_progress"):
                        deadline_str = entry.get("deadline") or entry.get("due_date")
                        if deadline_str:
                            try:
                                deadline = datetime.fromisoformat(deadline_str)
                                if deadline.tzinfo is None:
                                    deadline = deadline.replace(tzinfo=timezone.utc)
                                if deadline < now:
                                    entry["status"] = "expired"
                                    entry["updated_at"] = now.isoformat()
                                    changed += 1
                            except ValueError:
                                pass
                    updated.append(json.dumps(entry, ensure_ascii=False))
                queue_path.write_text("\n".join(updated) + "\n", encoding="utf-8")
                if changed:
                    logger.info("task_queue cleanup: %s — %d tasks expired", anima_name, changed)
                    total_expired += changed
            except Exception:
                logger.exception("task_queue cleanup failed for %s", anima_name)

        logger.info("task_queue stale cleanup complete: %d total tasks expired", total_expired)

    async def _run_episodes_rotation(self, keep_days: int = 7) -> None:
        """Delete episodes older than ``keep_days`` days for all animas.

        Runs daily at 03:30 JST. Keeps the most recent 7 days of episodes and
        removes everything older, including ``recovered_*`` files.
        """
        import re
        from datetime import date, timedelta

        logger.info("Starting system-wide episodes rotation (keep=%d days)", keep_days)
        cutoff = date.today() - timedelta(days=keep_days)
        date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        total_deleted = 0

        for anima_name, anima_dir in self._iter_consolidation_targets():
            episodes_dir = anima_dir / "episodes"
            if not episodes_dir.exists():
                continue
            for md_file in episodes_dir.rglob("*.md"):
                stem = md_file.stem
                # Delete recovered_* files unconditionally
                if stem.startswith("recovered_"):
                    md_file.unlink()
                    total_deleted += 1
                    logger.debug("Episodes rotation: deleted recovered file %s", md_file)
                    continue
                # Delete date files older than cutoff
                if date_pattern.match(stem):
                    try:
                        file_date = date.fromisoformat(stem)
                        if file_date < cutoff:
                            md_file.unlink()
                            total_deleted += 1
                            logger.debug("Episodes rotation: deleted %s", md_file)
                    except ValueError:
                        pass

        logger.info("Episodes rotation complete: %d files deleted", total_deleted)

    async def _run_knowledge_rotation(self, keep_days: int = 7) -> None:
        """Delete dated knowledge files older than ``keep_days`` days for all animas.

        Runs daily at 03:35 JST (just after episodes rotation).
        Targets files whose name contains a date pattern (YYYY-MM-DD or YYYYMMDD)
        anywhere in the filename. Scans recursively including archive/ subdirectories.
        Non-dated files are never deleted.
        """
        import re
        from datetime import date, timedelta

        logger.info("Starting system-wide knowledge rotation (keep=%d days)", keep_days)
        cutoff = date.today() - timedelta(days=keep_days)
        iso_pattern = re.compile(r"(\d{4}-\d{2}-\d{2})")
        compact_pattern = re.compile(r"(?<!\d)(\d{8})(?!\d)")
        total_deleted = 0

        for anima_name, anima_dir in self._iter_consolidation_targets():
            knowledge_dir = anima_dir / "knowledge"
            if not knowledge_dir.exists():
                continue
            for md_file in knowledge_dir.rglob("*.md"):
                stem = md_file.stem
                file_date = None

                # Priority 1: ISO format YYYY-MM-DD
                m = iso_pattern.search(stem)
                if m:
                    try:
                        file_date = date.fromisoformat(m.group(1))
                    except ValueError:
                        pass

                # Priority 2: Compact format YYYYMMDD
                if file_date is None:
                    m = compact_pattern.search(stem)
                    if m:
                        raw = m.group(1)
                        try:
                            file_date = date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
                        except ValueError:
                            pass

                if file_date is not None and file_date < cutoff:
                    try:
                        md_file.unlink()
                        total_deleted += 1
                        logger.debug(
                            "Knowledge rotation: deleted %s/%s",
                            anima_name, md_file.relative_to(anima_dir),
                        )
                    except OSError:
                        logger.exception(
                            "Knowledge rotation: failed to delete %s/%s",
                            anima_name, md_file.relative_to(anima_dir),
                        )

        logger.info("Knowledge rotation complete: %d files deleted", total_deleted)

    async def _run_engagement_log_rotation(self, keep_days: int = 30) -> None:
        """Trim dated sections from engagement_log.md for all animas.

        Runs monthly on the 1st at 04:00 JST.
        Scans for files named 'engagement_log.md' in each anima's knowledge/
        directory and removes sections (## YYYY-MM-DD ...) older than keep_days.
        The file header (lines before the first ## section) is always preserved.
        """
        import re
        from datetime import date, timedelta

        logger.info("Starting engagement log rotation (keep=%d days)", keep_days)
        cutoff = date.today() - timedelta(days=keep_days)
        section_date_pattern = re.compile(r"^## (\d{4}-\d{2}-\d{2})")
        total_trimmed = 0

        for anima_name, anima_dir in self._iter_consolidation_targets():
            log_path = anima_dir / "knowledge" / "engagement_log.md"
            if not log_path.exists():
                continue
            try:
                lines = log_path.read_text(encoding="utf-8").splitlines(keepends=True)

                # Separate header (lines before first ## section)
                header_lines: list[str] = []
                section_lines: list[str] = []
                in_header = True
                for line in lines:
                    if in_header and section_date_pattern.match(line):
                        in_header = False
                    if in_header:
                        header_lines.append(line)
                    else:
                        section_lines.append(line)

                # Split into sections and keep only those >= cutoff
                current_section: list[str] = []
                current_date: date | None = None
                kept_sections: list[list[str]] = []

                for line in section_lines:
                    match = section_date_pattern.match(line)
                    if match:
                        if current_section:
                            if current_date is not None and current_date >= cutoff:
                                kept_sections.append(current_section)
                        current_section = [line]
                        try:
                            current_date = date.fromisoformat(match.group(1))
                        except ValueError:
                            current_date = None
                    else:
                        current_section.append(line)

                # Handle last section
                if current_section:
                    if current_date is not None and current_date >= cutoff:
                        kept_sections.append(current_section)

                original_count = sum(
                    1 for line in section_lines if section_date_pattern.match(line)
                )
                kept_count = len(kept_sections)

                if kept_count < original_count:
                    new_content = "".join(header_lines) + "".join(
                        "".join(s) for s in kept_sections
                    )
                    log_path.write_text(new_content, encoding="utf-8")
                    removed = original_count - kept_count
                    total_trimmed += removed
                    logger.info(
                        "Engagement log rotation for %s: removed %d sections",
                        anima_name, removed,
                    )
            except Exception:
                logger.exception("Engagement log rotation failed for %s", anima_name)

        logger.info("Engagement log rotation complete: %d sections removed", total_trimmed)

    async def _run_activity_log_rotation(self) -> None:
        """Run activity log rotation for all animas."""
        logger.info("Starting system-wide activity log rotation")

        activity_cfg = self._load_config_attr("activity_log", "activity log rotation")

        from core.config.models import ActivityLogConfig
        defaults = ActivityLogConfig()
        mode = getattr(activity_cfg, "rotation_mode", defaults.rotation_mode) if activity_cfg else defaults.rotation_mode
        max_size_mb = getattr(activity_cfg, "max_size_mb", defaults.max_size_mb) if activity_cfg else defaults.max_size_mb
        max_age_days = getattr(activity_cfg, "max_age_days", defaults.max_age_days) if activity_cfg else defaults.max_age_days

        try:
            from core.memory.activity import ActivityLogger

            results = ActivityLogger.rotate_all(
                self.animas_dir,
                mode=mode,
                max_size_mb=max_size_mb,
                max_age_days=max_age_days,
            )
            if results:
                total_freed = sum(r.get("freed_bytes", 0) for r in results.values())
                total_deleted = sum(r.get("deleted_files", 0) for r in results.values())
                logger.info(
                    "Activity log rotation complete: %d animas, %d files deleted, %d bytes freed",
                    len(results), total_deleted, total_freed,
                )
            else:
                logger.info("Activity log rotation: no files needed rotation")
        except Exception:
            logger.exception("Activity log rotation failed")
