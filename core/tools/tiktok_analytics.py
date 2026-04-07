# AnimaWorks - Digital Anima Framework
# Copyright (C) 2026 AnimaWorks Authors
# SPDX-License-Identifier: Apache-2.0

"""TikTok analytics and engagement tracking tool for AnimaWorks.

Fetches engagement data and generates performance reports.
Used by maru (TikTok事業部リーダー).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.tools._base import logger

# ── Execution Profile ─────────────────────────────────────

EXECUTION_PROFILE: dict[str, dict[str, object]] = {
    "tiktok_record_engagement": {"expected_seconds": 5, "background_eligible": False},
    "tiktok_weekly_report": {"expected_seconds": 10, "background_eligible": False},
    "tiktok_get_performance": {"expected_seconds": 5, "background_eligible": False},
    "tiktok_scrape_engagement": {"expected_seconds": 60, "background_eligible": False},
}

# ── Tool Schemas ──────────────────────────────────────────


def get_tool_schemas() -> list[dict]:
    return [
        {
            "name": "tiktok_record_engagement",
            "description": (
                "TikTok投稿のエンゲージメントデータを記録する。"
                "投稿タイトル・URL・各指標を保存し、knowledge/に蓄積する。"
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "投稿タイトル"},
                    "tiktok_url": {"type": "string", "description": "TikTok投稿URL"},
                    "views": {"type": "integer", "description": "視聴回数"},
                    "saves": {"type": "integer", "description": "保存数"},
                    "likes": {"type": "integer", "description": "いいね数"},
                    "comments": {"type": "integer", "description": "コメント数"},
                    "shares": {"type": "integer", "description": "シェア数"},
                    "avg_watch_sec": {"type": "number", "description": "平均視聴時間（秒）"},
                    "full_view_pct": {"type": "number", "description": "フル視聴率（%）"},
                    "posted_at": {"type": "string", "description": "投稿日時（ISO形式）"},
                },
                "required": ["title", "views"],
            },
        },
        {
            "name": "tiktok_weekly_report",
            "description": (
                "蓄積されたエンゲージメントデータから週次パフォーマンスレポートを生成する。"
                "保存率・シェア数を重視したKPIサマリーを返す。"
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "weeks_back": {
                        "type": "integer",
                        "description": "何週間分のデータを集計するか（デフォルト1）",
                    },
                },
                "required": [],
            },
        },
        {
            "name": "tiktok_get_performance",
            "description": (
                "直近のTikTokパフォーマンスデータを取得する。"
                "最新の投稿実績とKPI推移を返す。"
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "取得する投稿数（デフォルト10）",
                    },
                },
                "required": [],
            },
        },
        {
            "name": "tiktok_scrape_engagement",
            "description": (
                "TikTok Studioからエンゲージメントデータを自動スクレイピングする。"
                "Playwrightで認証済みCookieを使いContentページから各指標を取得し記録する。"
                "cron command経由での自動実行を想定。"
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "cookie_path": {
                        "type": "string",
                        "description": "Cookie JSONファイルのパス（省略時: ~/.animaworks/credentials/tiktok_cookies.json）",
                    },
                    "max_posts": {
                        "type": "integer",
                        "description": "取得する最大投稿数（デフォルト20）",
                    },
                },
                "required": [],
            },
        },
    ]


# ── Data Storage ──────────────────────────────────────────


def _get_engagement_db(anima_dir: str | None = None) -> Path:
    """Get the path to the engagement database."""
    if anima_dir:
        db_path = Path(anima_dir) / "knowledge" / "tiktok_engagement.jsonl"
    else:
        from core.paths import get_data_dir
        db_path = get_data_dir() / "shared" / "tiktok_engagement.jsonl"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def _load_records(db_path: Path) -> list[dict]:
    """Load all engagement records."""
    if not db_path.exists():
        return []
    records = []
    for line in db_path.read_text(encoding="utf-8").strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return records


def _is_duplicate(db_path: Path, tiktok_url: str, today: str) -> bool:
    """Check if this URL was already recorded today."""
    for r in _load_records(db_path):
        if (r.get("tiktok_url") == tiktok_url
                and r.get("recorded_at", "").startswith(today)):
            return True
    return False


# ── Implementation ────────────────────────────────────────


def record_engagement(args: dict, anima_dir: str | None = None) -> dict:
    """Record engagement data for a TikTok post."""
    db_path = _get_engagement_db(anima_dir)
    now = datetime.now(timezone.utc).isoformat()

    record = {
        "recorded_at": now,
        "title": args.get("title", ""),
        "tiktok_url": args.get("tiktok_url", ""),
        "views": args.get("views", 0),
        "saves": args.get("saves", 0),
        "likes": args.get("likes", 0),
        "comments": args.get("comments", 0),
        "shares": args.get("shares", 0),
        "avg_watch_sec": args.get("avg_watch_sec", 0),
        "full_view_pct": args.get("full_view_pct", 0),
        "posted_at": args.get("posted_at", ""),
    }

    # Calculate save rate
    if record["views"] > 0:
        record["save_rate"] = round(record["saves"] / record["views"] * 100, 2)
    else:
        record["save_rate"] = 0

    # Append to JSONL
    with open(db_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # Also update knowledge summary
    if anima_dir:
        _update_feedback_knowledge(anima_dir)

    return {
        "success": True,
        "message": f"エンゲージメント記録完了: {record['title']}",
        "save_rate": record["save_rate"],
    }


def weekly_report(weeks_back: int = 1, anima_dir: str | None = None) -> dict:
    """Generate a weekly performance report."""
    db_path = _get_engagement_db(anima_dir)
    records = _load_records(db_path)

    if not records:
        return {
            "success": True,
            "message": "エンゲージメントデータがまだありません",
            "report": None,
        }

    # Sort by recorded_at descending
    records.sort(key=lambda r: r.get("recorded_at", ""), reverse=True)

    # Take records from the last N weeks
    total_views = sum(r.get("views", 0) for r in records)
    total_saves = sum(r.get("saves", 0) for r in records)
    total_likes = sum(r.get("likes", 0) for r in records)
    total_shares = sum(r.get("shares", 0) for r in records)
    total_comments = sum(r.get("comments", 0) for r in records)

    avg_save_rate = round(total_saves / total_views * 100, 2) if total_views > 0 else 0
    avg_full_view = 0
    full_view_records = [r for r in records if r.get("full_view_pct", 0) > 0]
    if full_view_records:
        avg_full_view = round(
            sum(r["full_view_pct"] for r in full_view_records) / len(full_view_records), 1
        )

    # Top performing posts
    top_posts = sorted(records, key=lambda r: r.get("save_rate", 0), reverse=True)[:3]

    report = {
        "period": f"直近{weeks_back}週間",
        "total_posts": len(records),
        "total_views": total_views,
        "total_saves": total_saves,
        "total_likes": total_likes,
        "total_shares": total_shares,
        "total_comments": total_comments,
        "avg_save_rate": avg_save_rate,
        "avg_full_view_pct": avg_full_view,
        "top_posts_by_save_rate": [
            {"title": p.get("title", ""), "save_rate": p.get("save_rate", 0), "views": p.get("views", 0)}
            for p in top_posts
        ],
    }

    return {
        "success": True,
        "message": f"週次レポート生成完了（{len(records)}投稿）",
        "report": report,
    }


def get_performance(limit: int = 10, anima_dir: str | None = None) -> dict:
    """Get recent performance data."""
    db_path = _get_engagement_db(anima_dir)
    records = _load_records(db_path)
    records.sort(key=lambda r: r.get("recorded_at", ""), reverse=True)

    return {
        "success": True,
        "count": len(records[:limit]),
        "total_records": len(records),
        "posts": records[:limit],
    }


def scrape_engagement(args: dict, anima_dir: str | None = None) -> dict:
    """Scrape engagement data from TikTok Studio using Playwright."""
    max_posts = args.get("max_posts", 20)
    cookie_path = args.get("cookie_path")

    try:
        from core.tools._tiktok_scraper import (
            load_cookies, validate_cookies, scrape_tiktok_studio,
            CookieNotFoundError, CookieExpiredError, PageStructureError,
            DEFAULT_COOKIE_PATH,
        )
    except ImportError:
        return {
            "success": False,
            "error": "dependency_missing",
            "message": "playwright未インストール: pip install playwright && playwright install chromium",
        }

    # Load and validate cookies
    cpath = Path(cookie_path) if cookie_path else DEFAULT_COOKIE_PATH
    try:
        cookies = load_cookies(cpath)
        if not validate_cookies(cookies):
            return {
                "success": False,
                "error": "cookie_expired",
                "message": "TikTok Cookieが期限切れです。Chrome拡張でCookieを再エクスポートしてください。",
            }
    except CookieNotFoundError:
        return {
            "success": False,
            "error": "cookie_not_found",
            "message": f"Cookieファイルが見つかりません: {cpath}",
        }

    # Scrape with retry
    db_path = _get_engagement_db(anima_dir)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for attempt in range(2):
        try:
            posts = scrape_tiktok_studio(cookies, max_posts=max_posts)
            break
        except CookieExpiredError as e:
            return {
                "success": False,
                "error": "cookie_expired",
                "message": f"セッション切れ: {e}",
            }
        except PageStructureError as e:
            logger.error("TikTok Studio page structure changed: %s", e)
            return {
                "success": False,
                "error": "page_structure_changed",
                "message": f"ページ構造変更検出: {e}",
            }
        except Exception as e:
            if attempt == 0:
                logger.warning("Scrape attempt 1 failed, retrying: %s", e)
                import time as _time
                _time.sleep(5)
            else:
                return {
                    "success": False,
                    "error": "network_error",
                    "message": f"スクレイピング失敗（リトライ済み）: {e}",
                }

    # Record each post (with dedup)
    recorded = 0
    skipped = 0
    for post in posts:
        url = post.get("tiktok_url", "")
        if url and _is_duplicate(db_path, url, today):
            skipped += 1
            continue
        record_engagement(post, anima_dir=anima_dir)
        recorded += 1

    return {
        "success": True,
        "message": f"スクレイピング完了: {recorded}件記録, {skipped}件スキップ（重複）",
        "recorded": recorded,
        "skipped": skipped,
        "total_scraped": len(posts),
    }


def _update_feedback_knowledge(anima_dir: str) -> None:
    """Update feedback_insights in knowledge based on accumulated data."""
    db_path = _get_engagement_db(anima_dir)
    records = _load_records(db_path)

    if len(records) < 3:
        return  # Not enough data for insights

    # Sort by save_rate
    records_with_rate = [r for r in records if r.get("save_rate", 0) > 0]
    if not records_with_rate:
        return

    records_with_rate.sort(key=lambda r: r["save_rate"], reverse=True)

    # Extract top themes from titles
    top_titles = [r["title"] for r in records_with_rate[:5]]

    insights = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "top_posts_by_save_rate": [
            {"title": r["title"], "save_rate": r["save_rate"], "views": r["views"]}
            for r in records_with_rate[:5]
        ],
        "avg_save_rate": round(
            sum(r["save_rate"] for r in records_with_rate) / len(records_with_rate), 2
        ),
        "total_posts_tracked": len(records),
    }

    out_path = Path(anima_dir) / "knowledge" / "feedback_insights_auto.json"
    out_path.write_text(json.dumps(insights, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Dispatch ──────────────────────────────────────────────


def dispatch(name: str, args: dict[str, Any]) -> Any:
    anima_dir = args.pop("anima_dir", None)

    if name == "tiktok_record_engagement":
        return record_engagement(args, anima_dir=anima_dir)

    if name == "tiktok_weekly_report":
        return weekly_report(
            weeks_back=args.get("weeks_back", 1),
            anima_dir=anima_dir,
        )

    if name == "tiktok_get_performance":
        return get_performance(
            limit=args.get("limit", 10),
            anima_dir=anima_dir,
        )

    if name == "tiktok_scrape_engagement":
        return scrape_engagement(args, anima_dir=anima_dir)

    raise ValueError(f"Unknown tool: {name}")
