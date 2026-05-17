from __future__ import annotations

"""tiktok_verify_image_freshness — 画像とドラフトJSONの整合性チェック.

ドラフトJSONの `saved_at` と各スライド画像のmtimeを比較し、
画像がJSONより古ければ stale と判定する。
納品前にmaruから呼び出すことで「JSONだけ修正、画像は古いまま」事故を防ぐ。
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _get_draft_dir() -> Path:
    from core.paths import get_data_dir

    return get_data_dir() / "tiktok_drafts"


def _get_image_dir() -> Path:
    from core.paths import get_data_dir

    return get_data_dir() / "tiktok_images"


def _parse_iso(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def verify_image_freshness(draft_id: str) -> dict:
    """Check whether all slide images are newer than the draft JSON's saved_at.

    Args:
        draft_id: e.g. "draft_20260508_morning" or "draft_20260508_morning.json"

    Returns:
        {
          "success": bool,
          "verdict": "fresh" | "stale" | "missing",
          "saved_at": iso str,
          "slides": [{"slide": 1, "path": "...", "mtime": "...", "fresh": bool}, ...],
          "stale_slides": [1, 3],   # 1-indexed
          "message": str,
        }
    """
    stem = draft_id.replace(".json", "")
    draft_path = _get_draft_dir() / f"{stem}.json"
    if not draft_path.exists():
        return {
            "success": False,
            "verdict": "missing",
            "message": f"ドラフトJSONが見つかりません: {draft_path}",
        }

    try:
        draft = json.loads(draft_path.read_text())
    except Exception as e:
        return {
            "success": False,
            "verdict": "missing",
            "message": f"ドラフトJSON読み込み失敗: {e}",
        }

    saved_at_str = draft.get("saved_at", "")
    saved_at = _parse_iso(saved_at_str)
    if saved_at is None:
        return {
            "success": False,
            "verdict": "missing",
            "message": f"saved_at がパース不能: {saved_at_str!r}",
        }

    img_dir = _get_image_dir() / stem
    if not img_dir.is_dir():
        return {
            "success": False,
            "verdict": "missing",
            "saved_at": saved_at_str,
            "message": f"画像ディレクトリが存在しません: {img_dir}",
        }

    # Pick the newest png per slide index (slide_1_xxxxxx.png is the canonical name).
    # Ignore _backup_ subdirs and .jpg thumbnails (jpg may be stale on purpose).
    by_slide: dict[int, Path] = {}
    for p in img_dir.glob("slide_*.png"):
        if "_backup_" in str(p):
            continue
        # Filename forms: slide_1.png  or  slide_1_3aa95c.png
        try:
            idx = int(p.stem.split("_")[1])
        except (IndexError, ValueError):
            continue
        existing = by_slide.get(idx)
        if existing is None or p.stat().st_mtime > existing.stat().st_mtime:
            by_slide[idx] = p

    slides = []
    stale_slides = []
    missing_slides = []
    for i in range(1, 6):
        p = by_slide.get(i)
        if p is None:
            missing_slides.append(i)
            slides.append({"slide": i, "path": None, "mtime": None, "fresh": False})
            continue
        mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
        fresh = mtime >= saved_at
        slides.append(
            {
                "slide": i,
                "path": str(p),
                "mtime": mtime.isoformat(),
                "fresh": fresh,
            }
        )
        if not fresh:
            stale_slides.append(i)

    if missing_slides:
        return {
            "success": False,
            "verdict": "missing",
            "saved_at": saved_at_str,
            "slides": slides,
            "stale_slides": stale_slides,
            "missing_slides": missing_slides,
            "message": f"スライド {missing_slides} の画像が見つかりません",
        }

    if stale_slides:
        return {
            "success": False,
            "verdict": "stale",
            "saved_at": saved_at_str,
            "slides": slides,
            "stale_slides": stale_slides,
            "message": (
                f"スライド {stale_slides} の画像が saved_at({saved_at_str}) より古いです。"
                "tama に画像再生成を差し戻してください。"
            ),
        }

    return {
        "success": True,
        "verdict": "fresh",
        "saved_at": saved_at_str,
        "slides": slides,
        "stale_slides": [],
        "message": "全5枚の画像が saved_at 以降に生成されています。納品OK。",
    }


def get_tool_schemas() -> list[dict]:
    return [
        {
            "name": "tiktok_verify_image_freshness",
            "description": (
                "TikTokカルーセルの画像とドラフトJSONの整合性をチェックする。"
                "各スライド画像のmtimeがドラフトJSONのsaved_at以降かを比較し、"
                "古い画像があれば verdict=stale を返す。"
                "judge合格後、Telegram納品の直前に必ず呼ぶこと。"
                "stale が返ったら tama に画像再生成を差し戻す。"
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "draft_id": {
                        "type": "string",
                        "description": (
                            "ドラフトID（例: draft_20260508_morning または "
                            "draft_20260508_morning.json）"
                        ),
                    },
                },
                "required": ["draft_id"],
            },
        },
    ]


def dispatch(name: str, args: dict[str, Any]) -> Any:
    args.pop("anima_dir", None)
    if name == "tiktok_verify_image_freshness":
        return verify_image_freshness(draft_id=args["draft_id"])
    raise ValueError(f"Unknown tool: {name}")
