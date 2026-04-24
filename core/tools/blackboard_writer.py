from __future__ import annotations
# AnimaWorks - Digital Anima Framework
# Copyright (C) 2026 AnimaWorks Authors
# SPDX-License-Identifier: Apache-2.0

"""Blackboard writer — updates shared/blackboard/organization_status.md.

Pulls live KPI (X follower count via X API) and static goals (from
common_knowledge/organization/goals.md), computes pace-to-goal, and writes
the merged snapshot atomically to the blackboard so every Anima sees the
same number in the next heartbeat.

Cron-only tool (``type: command`` with ``trigger_heartbeat: false``).
"""

import calendar
import logging
import os
import re
import time
from datetime import date
from pathlib import Path
from typing import Any

from core.paths import get_common_knowledge_dir, get_shared_dir
from core.time_utils import now_jst
from core.tools.x_search import XSearchClient

logger = logging.getLogger("animaworks.tools.blackboard_writer")


# Username for the TrinityDox X account. Kept as a constant — change here if
# the handle ever moves. Overridable via env var for testing.
_DEFAULT_X_HANDLE = os.environ.get("ANIMAWORKS_X_HANDLE", "TrinityDox_JP")


# ── goals.md parsing ─────────────────────────────────────

_RE_X_FOLLOWER_ROW = re.compile(
    r"\|\s*Xフォロワー数\s*\|\s*([\d,]+)\s*\|\s*([\d,]+)\s*\|\s*([\d,]+)\s*\|\s*\*?\*?([\d,]+)\*?\*?\s*\|"
)

# Section header patterns: start of the X unit, start of any *other* ``##``
# unit header. We pin follower-row matching to the X section so adding a
# future table that reuses ``Xフォロワー数`` elsewhere does not flip the goal
# numbers (Codex review m2).
_RE_X_SECTION_START = re.compile(r"^##\s*X事業部\b", re.MULTILINE)
_RE_ANY_H2_START = re.compile(r"^##\s+\S", re.MULTILINE)


def _extract_x_section(text: str) -> str:
    """Return the slice of goals.md between ``## X事業部`` and the next h2.

    Falls back to the whole document if the header is missing so older
    goals.md layouts still parse.
    """
    start_match = _RE_X_SECTION_START.search(text)
    if not start_match:
        return text
    start = start_match.end()
    next_match = _RE_ANY_H2_START.search(text, pos=start)
    end = next_match.start() if next_match else len(text)
    return text[start:end]


def _parse_goals(goals_path: Path) -> dict[str, int]:
    """Extract X follower goals from goals.md.

    Returns dict with keys ``baseline``, ``month1``, ``month2``, ``month3``.
    Missing / malformed file degrades to zeros.
    """
    try:
        text = goals_path.read_text(encoding="utf-8")
    except Exception:
        logger.debug("goals.md read failed", exc_info=True)
        return {"baseline": 0, "month1": 0, "month2": 0, "month3": 0}

    # Scan only the X事業部 section to avoid matching rows from other units
    # (e.g. TikTok) that happen to repeat the same label in the future.
    section = _extract_x_section(text)
    m = _RE_X_FOLLOWER_ROW.search(section)
    if not m:
        logger.warning("goals.md does not match X follower row regex")
        return {"baseline": 0, "month1": 0, "month2": 0, "month3": 0}

    def _n(s: str) -> int:
        return int(s.replace(",", ""))

    return {
        "baseline": _n(m.group(1)),
        "month1": _n(m.group(2)),
        "month2": _n(m.group(3)),
        "month3": _n(m.group(4)),
    }


# ── Stale fallback (M2) ───────────────────────────────────
#
# When the X API call fails we must NOT overwrite the blackboard with
# followers=0 — every Anima would then read "current: 0" and treat it as
# ground truth. Instead we read the previously persisted value from the
# existing blackboard file (if any) and keep it, while annotating the
# markdown with a clear "stale" marker so the LLM can see the fetch
# failed.

_RE_PREVIOUS_FOLLOWERS = re.compile(
    r"\|\s*X\s*フォロワー(?:数)?（今月末目標）\s*\|\s*[\d,]+\s*\|\s*([\d,]+)\s*\|"
)


def _load_previous_followers(target: Path) -> int | None:
    """Read the previously recorded followers count from the blackboard.

    Returns ``None`` if the file does not exist or the count cannot be
    parsed. Any exception degrades to ``None`` silently.
    """
    try:
        if not target.is_file():
            return None
        text = target.read_text(encoding="utf-8")
    except Exception:
        return None
    m = _RE_PREVIOUS_FOLLOWERS.search(text)
    if not m:
        return None
    try:
        return int(m.group(1).replace(",", ""))
    except (TypeError, ValueError):
        return None


# ── Pace calculation ──────────────────────────────────────

def _days_left_in_month(today: date) -> int:
    last_day = calendar.monthrange(today.year, today.month)[1]
    remaining = last_day - today.day
    return max(remaining, 1)  # Avoid divide-by-zero on the last day


def _pace_to_goal(current: int, goal: int, days_left: int) -> float:
    if goal <= current:
        return 0.0
    return (goal - current) / days_left


# ── Rendering ─────────────────────────────────────────────

def _render_markdown(
    ts: str,
    handle: str,
    followers: int,
    goals: dict[str, int],
    pace: float,
    days_left: int,
) -> str:
    month_goal = goals.get("month1", 0)
    remaining = max(month_goal - followers, 0)
    lines: list[str] = []
    lines.append(f"# 組織状況（最終更新: {ts}）\n")
    lines.append("<!-- Auto-generated by core.tools.blackboard_writer. Do not edit by hand. -->\n")
    lines.append("## X事業部 KPI\n")
    lines.append(f"対象アカウント: `@{handle}`\n")
    lines.append("| 指標 | 目標 | 現在 | 残差 | 月末までの必要ペース |")
    lines.append("|------|------|------|------|----------------------|")
    lines.append(
        f"| Xフォロワー（今月末目標） | {month_goal} | {followers} | {remaining} | "
        f"{pace:.2f}/day（残り{days_left}日） |"
    )
    lines.append(
        f"| Xフォロワー（2ヶ月後） | {goals.get('month2', 0)} | {followers} | "
        f"{max(goals.get('month2', 0) - followers, 0)} | — |"
    )
    lines.append(
        f"| Xフォロワー（3ヶ月後） | {goals.get('month3', 0)} | {followers} | "
        f"{max(goals.get('month3', 0) - followers, 0)} | — |"
    )
    lines.append("")
    lines.append("## 今月末目標までの距離（一目で）\n")
    if remaining == 0:
        lines.append(f"**✅ 今月末目標（{month_goal}人）達成済み**")
    else:
        lines.append(
            f"**残 {remaining} 人 / {days_left} 日 → 1日あたり {pace:.1f} 人獲得が必要**"
        )
    lines.append("")
    lines.append("## 直近のBlocker\n")
    lines.append("（ブラックボードには未記載。詳細は各Animaのstate/pending参照）")
    lines.append("")
    return "\n".join(lines)


# ── Public API ────────────────────────────────────────────

def update_org_status(anima_dir: str = "") -> dict[str, Any]:
    """Fetch live KPIs and atomically rewrite organization_status.md.

    Returns summary dict for logging. Never raises — failures are logged and
    an error marker is placed in the blackboard so downstream Anima can see
    the issue instead of silently reading stale data.
    """
    ts = now_jst().strftime("%Y-%m-%d %H:%M JST")
    today = now_jst().date()
    days_left = _days_left_in_month(today)
    handle = _DEFAULT_X_HANDLE

    goals = _parse_goals(get_common_knowledge_dir() / "organization" / "goals.md")

    # Atomic write target (needed early for the stale fallback path below).
    target = get_shared_dir() / "blackboard" / "organization_status.md"

    followers = 0
    fetch_error: str | None = None
    stale = False
    try:
        client = XSearchClient()
        metrics = client.get_user_metrics(handle)
        if metrics:
            followers = int(metrics.get("followers_count", 0))
        else:
            fetch_error = f"User @{handle} not found"
    except Exception as e:
        fetch_error = f"{type(e).__name__}: {e}"
        logger.warning("X API follower fetch failed: %s", fetch_error)

    # On fetch failure, keep the previously-persisted value instead of
    # clobbering the blackboard with zero. See Codex review M2.
    if fetch_error:
        previous = _load_previous_followers(target)
        if previous is not None:
            followers = previous
            stale = True

    pace = _pace_to_goal(followers, goals.get("month1", 0), days_left)
    body = _render_markdown(ts, handle, followers, goals, pace, days_left)

    if fetch_error:
        if stale:
            body += (
                "\n---\n\n"
                f"⚠️ **KPI取得に失敗しました** (`{fetch_error}`)。"
                f"表示中のフォロワー数は前回成功時の値 ({followers}) です（stale）。"
                "\n"
            )
        else:
            body += (
                "\n---\n\n"
                f"⚠️ **KPI取得に失敗しました** (`{fetch_error}`)。"
                "前回の成功値も見つからなかったため、数値は未確定 (0) 扱いです。"
                "\n"
            )

    # Atomic write: tmp + rename. Unique suffix (PID + monotonic ns) avoids
    # concurrent writers clobbering the same ``.tmp`` file (Codex review M3).
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(f"{target.suffix}.{os.getpid()}.{time.monotonic_ns()}.tmp")
    try:
        tmp.write_text(body, encoding="utf-8")
        os.replace(tmp, target)
    except Exception:
        # Best-effort cleanup of the tmp file if rename failed.
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        raise

    summary = {
        "ok": fetch_error is None,
        "followers": followers,
        "stale": stale,
        "pace": round(pace, 2),
        "days_left": days_left,
        "target": str(target),
        "error": fetch_error,
    }
    logger.info("Blackboard updated: %s", summary)
    return summary


# ── Anthropic tool_use schemas ────────────────────────────

def get_tool_schemas() -> list[dict]:
    return [
        {
            "name": "blackboard_update_org_status",
            "description": (
                "Refresh shared/blackboard/organization_status.md with the latest "
                "X follower count and goal progress. Cron-only. "
                "Takes no arguments."
            ),
            "input_schema": {
                "type": "object",
                "properties": {},
            },
        },
    ]


# ── Dispatch ──────────────────────────────────────────────

def dispatch(name: str, args: dict[str, Any]) -> Any:
    if name == "blackboard_update_org_status":
        anima_dir = args.get("anima_dir", "")
        return update_org_status(anima_dir=anima_dir)
    raise ValueError(f"Unknown tool: {name}")
