# AnimaWorks - Digital Anima Framework
# Copyright (C) 2026 AnimaWorks Authors
# SPDX-License-Identifier: Apache-2.0

"""TikTok carousel content planning tool for AnimaWorks.

Generates 5-slide carousel plans with VSEO optimization.
Used by tama (TikTok制作担当).
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
    "tiktok_plan_carousel": {"expected_seconds": 30, "background_eligible": False},
    "tiktok_save_draft": {"expected_seconds": 5, "background_eligible": False},
    "tiktok_list_drafts": {"expected_seconds": 2, "background_eligible": False},
}

# ── Carousel Quality Validation ───────────────────────────

PROHIBITED_PHRASES = [
    "次で解説", "続きを見て", "次のスライドで", "次回",
    "AI副業", "AIで稼ぐ", "月5万", "月10万", "月3万",
    "ココナラ", "クラウドワークス", "ランサーズ",
    "プロンプト販売", "初期費用ゼロ",
]

ALLOWED_TOOLS = [
    "Claude", "ChatGPT", "Gemini", "Copilot", "Perplexity", "Grok",
    "Canva AI", "Notion AI", "DALL-E", "Midjourney", "ElevenLabs", "fal.ai",
]

MAX_CHARS_PER_LINE = 12


def _validate_carousel(plan: dict) -> list[str]:
    """Validate a carousel plan against production rules. Returns list of violations."""
    violations = []
    overlay_texts = plan.get("overlay_texts", [])

    # Check slide count
    if len(overlay_texts) != 5:
        violations.append(f"スライド数が{len(overlay_texts)}枚（5枚必須）")

    # Check prohibited phrases
    all_text = " ".join(overlay_texts) + " " + plan.get("tiktok_body", "")
    for phrase in PROHIBITED_PHRASES:
        if phrase in all_text:
            violations.append(f"禁止フレーズ検出: 「{phrase}」")

    # Check line length
    for i, text in enumerate(overlay_texts):
        for line in text.split("\\n"):
            # Count full-width chars as 1, half-width as 0.5
            char_count = sum(2 if ord(c) > 127 else 1 for c in line) / 2
            if char_count > MAX_CHARS_PER_LINE:
                violations.append(f"スライド{i+1}: 行が{char_count:.0f}文字（上限{MAX_CHARS_PER_LINE}文字）: {line[:20]}...")

    # Check prompts don't contain text instructions
    for i, prompt in enumerate(plan.get("prompts", [])):
        text_indicators = ["text", "word", "letter", "caption", "title", "headline", "テキスト", "文字"]
        if any(ind in prompt.lower() for ind in text_indicators):
            violations.append(f"スライド{i+1}: 画像プロンプトにテキスト指示を含む")

    return violations


# ── Tool Schemas ──────────────────────────────────────────


def get_tool_schemas() -> list[dict]:
    return [
        {
            "name": "tiktok_plan_carousel",
            "description": (
                "カルーセル企画のJSONを品質チェックする。"
                "5スライド構成・禁止フレーズ・テキスト長・画像プロンプトのルール違反を検出する。"
                "企画JSON自体はLLMが作成し、このツールでバリデーションする。"
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "plan_json": {
                        "type": "string",
                        "description": "カルーセル企画のJSON文字列（title, theme, overlay_texts, prompts, tiktok_body等）",
                    },
                },
                "required": ["plan_json"],
            },
        },
        {
            "name": "tiktok_save_draft",
            "description": (
                "バリデーション済みのカルーセル企画をドラフトとして保存する。"
                "保存後、ユーザーの承認を待つ。"
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "plan_json": {
                        "type": "string",
                        "description": "カルーセル企画のJSON文字列",
                    },
                    "slot": {
                        "type": "string",
                        "description": "投稿枠（morning / evening）",
                        "enum": ["morning", "evening"],
                    },
                },
                "required": ["plan_json", "slot"],
            },
        },
        {
            "name": "tiktok_list_drafts",
            "description": "保存済みのTikTokカルーセルドラフト一覧を取得する。",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    ]


# ── Implementation ────────────────────────────────────────


def plan_carousel(plan_json_str: str) -> dict:
    """Validate a carousel plan JSON."""
    try:
        plan = json.loads(plan_json_str)
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"JSONパースエラー: {e}"}

    violations = _validate_carousel(plan)

    if violations:
        return {
            "success": False,
            "valid": False,
            "violations": violations,
            "message": f"品質チェックNG: {len(violations)}件の違反",
        }

    return {
        "success": True,
        "valid": True,
        "violations": [],
        "message": "品質チェックOK: 全ルール準拠",
        "plan": plan,
    }


def save_draft(plan_json_str: str, slot: str, anima_dir: str | None = None) -> dict:
    """Save a validated carousel draft."""
    try:
        plan = json.loads(plan_json_str)
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"JSONパースエラー: {e}"}

    # Validate first
    violations = _validate_carousel(plan)
    if violations:
        return {
            "success": False,
            "error": "バリデーションエラーがあるため保存できません",
            "violations": violations,
        }

    # Determine save path
    from core.paths import get_data_dir
    draft_dir = get_data_dir() / "tiktok_drafts"
    draft_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y%m%d")
    filename = f"draft_{date_str}_{slot}.json"
    draft_path = draft_dir / filename

    plan["saved_at"] = now.isoformat()
    plan["slot"] = slot
    plan["status"] = "pending_approval"

    draft_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "success": True,
        "message": f"ドラフト保存完了: {filename}",
        "path": str(draft_path),
        "slot": slot,
    }


def list_drafts() -> dict:
    """List all saved drafts."""
    from core.paths import get_data_dir
    draft_dir = get_data_dir() / "tiktok_drafts"

    if not draft_dir.exists():
        return {"success": True, "drafts": [], "count": 0}

    drafts = []
    for f in sorted(draft_dir.glob("draft_*.json"), reverse=True):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            drafts.append({
                "filename": f.name,
                "title": d.get("title", ""),
                "theme": d.get("theme", ""),
                "slot": d.get("slot", ""),
                "status": d.get("status", "unknown"),
                "saved_at": d.get("saved_at", ""),
            })
        except Exception:
            pass

    return {"success": True, "drafts": drafts, "count": len(drafts)}


# ── Dispatch ──────────────────────────────────────────────


def dispatch(name: str, args: dict[str, Any]) -> Any:
    anima_dir = args.pop("anima_dir", None)

    if name == "tiktok_plan_carousel":
        return plan_carousel(args["plan_json"])

    if name == "tiktok_save_draft":
        return save_draft(args["plan_json"], args["slot"], anima_dir=anima_dir)

    if name == "tiktok_list_drafts":
        return list_drafts()

    raise ValueError(f"Unknown tool: {name}")
