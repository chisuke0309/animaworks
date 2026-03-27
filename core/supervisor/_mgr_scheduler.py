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
