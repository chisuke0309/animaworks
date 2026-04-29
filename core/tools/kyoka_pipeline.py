# AnimaWorks - Digital Anima Framework
# Copyright (C) 2026 AnimaWorks Authors
# SPDX-License-Identifier: Apache-2.0

"""End-to-end Kyoka scenario pipeline.

Given a theme + season + reference image, produces:
  1. A scenario spec (claude-sonnet-4-6 LLM call)
  2. 6 frame images + storyboard.png (kyoka_image.generate_six_frames)
  3. A new record in the Kyoka Scenarios Notion DB
     (f1d407fcb3d94ca78cd81ddbe2c11d67) with all fields populated

Used by:
  - sumi (Anima) at HB time when rin delegates a scenario
  - chisuke at the CLI for half-manual P2 prototyping
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from core.tools._base import get_credential, logger
from core.tools._kyoka_prompt_template import (
    build_full_prompts,
    parse_llm_json,
    validate_scenario_spec,
)
from core.tools.notion import NotionClient

# ── Constants ─────────────────────────────────────────────

KYOKA_DB_ID = "f1d407fcb3d94ca78cd81ddbe2c11d67"
DEFAULT_REFERENCE = (
    "~/.animaworks/common_knowledge/tiktok_templates/kyoka/assets/kyoka_closeup_001_start.jpg"
)
DEFAULT_ASSETS_ROOT = (
    "~/.animaworks/common_knowledge/tiktok_templates/kyoka/assets"
)
DEFAULT_LLM_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 8000

# ── Execution Profile ─────────────────────────────────────

EXECUTION_PROFILE: dict[str, dict[str, object]] = {
    "kyoka_pipeline_run": {"expected_seconds": 480, "background_eligible": True},
}


# ── Existing scenario fetch ─────────────────────────────────


def fetch_existing_scenarios(client: NotionClient | None = None) -> list[dict[str, Any]]:
    """Pull all existing rows from the Kyoka Scenarios DB.

    Returns a list of simplified dicts with keys: scenario_id, title_jp,
    season, frame_breakdown, posting_status, page_id.
    """
    client = client or NotionClient()
    result = client.query_database(database_id=KYOKA_DB_ID, page_size=100)
    rows = result.get("results", []) if isinstance(result, dict) else result
    out: list[dict[str, Any]] = []
    for row in rows:
        # Notion query_database returns a simplified structure via _extract_property_value;
        # NotionClient already flattens properties into top-level keys when possible.
        # Be tolerant: read both flattened and original-property forms.
        props = row.get("properties", row)
        out.append(
            {
                "page_id": row.get("page_id") or row.get("id"),
                "scenario_id": props.get("Scenario ID") or props.get("scenario_id"),
                "title_jp": props.get("Title (JP)") or props.get("title_jp"),
                "season": props.get("Season") or props.get("season"),
                "frame_breakdown": props.get("Frame Breakdown") or props.get("frame_breakdown"),
                "posting_status": props.get("Posting Status") or props.get("posting_status"),
            }
        )
    # Filter out blanks
    return [s for s in out if s.get("title_jp")]


def next_scenario_id(existing: list[dict[str, Any]]) -> str:
    """Compute the next kyoka_scenario_NNN id from existing rows."""
    pat = re.compile(r"kyoka_scenario_(\d+)")
    nums = []
    for s in existing:
        sid = s.get("scenario_id") or ""
        m = pat.match(sid)
        if m:
            nums.append(int(m.group(1)))
    n = (max(nums) + 1) if nums else 4
    return f"kyoka_scenario_{n:03d}"


# ── LLM call (Anthropic SDK) ────────────────────────────────


def call_claude_for_scenario(
    system_prompt: str,
    user_message: str,
    model: str = DEFAULT_LLM_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> str:
    """Call claude-sonnet-4-6 via the Anthropic SDK and return the raw text."""
    try:
        import anthropic  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "anthropic SDK not installed. Run `uv add anthropic` or check the project deps."
        ) from exc

    api_key = get_credential(
        credential_name="anthropic",
        tool_name="kyoka_pipeline",
        env_var="ANTHROPIC_API_KEY",
    )
    client = anthropic.Anthropic(api_key=api_key)

    logger.info("kyoka_pipeline: calling %s (max_tokens=%d)", model, max_tokens)
    t0 = time.time()
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    elapsed = time.time() - t0

    parts: list[str] = []
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    text = "".join(parts).strip()
    logger.info("kyoka_pipeline: LLM returned %d chars in %.1fs", len(text), elapsed)
    if not text:
        raise RuntimeError("LLM returned empty content")
    return text


# ── Notion record creation ──────────────────────────────────


def _chunk_rich_text(value: str, limit: int = 1900) -> list[dict[str, Any]]:
    """Split a long string into Notion rich_text chunks <= limit chars each.

    Notion API caps each rich_text token at 2000 chars; we use 1900 for safety.
    """
    if not value:
        return []
    return [
        {"text": {"content": value[i : i + limit]}}
        for i in range(0, len(value), limit)
    ]


def create_notion_record(
    spec: dict[str, Any],
    scenario_id: str,
    storyboard_filename: str,
    notes_extra: str = "",
    client: NotionClient | None = None,
) -> dict[str, Any]:
    """Create a new page in Kyoka Scenarios DB with all fields populated.

    Bypasses NotionClient.create_page so we can build chunked rich_text for
    long fields (GPT Image Prompt / Seedance Prompt routinely exceed 2000
    chars and must be split into multiple rich_text objects).
    """
    client = client or NotionClient()

    notes_full = (notes_extra + "\n\n" if notes_extra else "") + (
        spec.get("differentiation_note") or ""
    )
    season = spec.get("season") or "early_summer"

    properties: dict[str, Any] = {
        "Scenario ID": {"title": [{"text": {"content": scenario_id}}]},
        "Title (JP)": {"rich_text": _chunk_rich_text(spec.get("title_jp", ""))},
        "Season": {"select": {"name": season}},
        "Status": {"select": {"name": "画像済"}},
        "Frame Count": {"number": int(spec.get("frame_count", 6))},
        "Duration (sec)": {"number": int(spec.get("duration_sec", 15))},
        "Frame Breakdown": {"rich_text": _chunk_rich_text(spec.get("frame_breakdown", ""))},
        "GPT Image Prompt": {"rich_text": _chunk_rich_text(spec.get("gpt_image_prompt", ""))},
        "Seedance Prompt": {"rich_text": _chunk_rich_text(spec.get("seedance_prompt", ""))},
        "Storyboard Filename": {"rich_text": _chunk_rich_text(storyboard_filename)},
        "Video Filename": {"rich_text": _chunk_rich_text(scenario_id)},
        "BGM Notes": {"rich_text": _chunk_rich_text(spec.get("bgm_notes", ""))},
        "Notes": {"rich_text": _chunk_rich_text(notes_full.strip())},
        "TikTok Caption": {"rich_text": _chunk_rich_text(spec.get("tiktok_caption", ""))},
        "Instagram Caption": {"rich_text": _chunk_rich_text(spec.get("instagram_caption", ""))},
        "Posting Status": {"select": {"name": "未投稿"}},
    }
    body = {
        "parent": {"database_id": KYOKA_DB_ID},
        "properties": properties,
    }
    result = client._post("/pages", body)  # noqa: SLF001 — intentional: bypass create_page chunking
    return {"page_id": result["id"], "url": result.get("url", "")}


# ── Pipeline entry ──────────────────────────────────────────


def update_notion_record(
    page_id: str,
    spec: dict[str, Any],
    scenario_id: str,
    storyboard_filename: str,
    notes_extra: str = "",
    client: NotionClient | None = None,
) -> dict[str, Any]:
    """Update an existing Notion page with fresh spec data (redo mode)."""
    client = client or NotionClient()
    notes_full = (notes_extra + "\n\n" if notes_extra else "") + (spec.get("differentiation_note") or "")
    season = spec.get("season") or "early_summer"
    properties: dict[str, Any] = {
        "Title (JP)": {"rich_text": _chunk_rich_text(spec.get("title_jp", ""))},
        "Season": {"select": {"name": season}},
        "Status": {"select": {"name": "画像済"}},
        "Frame Count": {"number": int(spec.get("frame_count", 6))},
        "Duration (sec)": {"number": int(spec.get("duration_sec", 15))},
        "Frame Breakdown": {"rich_text": _chunk_rich_text(spec.get("frame_breakdown", ""))},
        "GPT Image Prompt": {"rich_text": _chunk_rich_text(spec.get("gpt_image_prompt", ""))},
        "Seedance Prompt": {"rich_text": _chunk_rich_text(spec.get("seedance_prompt", ""))},
        "Storyboard Filename": {"rich_text": _chunk_rich_text(storyboard_filename)},
        "Video Filename": {"rich_text": _chunk_rich_text(scenario_id)},
        "BGM Notes": {"rich_text": _chunk_rich_text(spec.get("bgm_notes", ""))},
        "Notes": {"rich_text": _chunk_rich_text(notes_full.strip())},
        "TikTok Caption": {"rich_text": _chunk_rich_text(spec.get("tiktok_caption", ""))},
        "Instagram Caption": {"rich_text": _chunk_rich_text(spec.get("instagram_caption", ""))},
    }
    result = client._patch(f"/pages/{page_id}", {"properties": properties})  # noqa: SLF001
    return {"page_id": result["id"], "url": result.get("url", "")}


def run_pipeline(
    theme: str,
    season: str,
    reference_path: Path,
    title_hint: str | None = None,
    market_pulse: str | None = None,
    assets_root: Path | None = None,
    dry_run: bool = False,
    skip_images: bool = False,
    skip_notion: bool = False,
    llm_model: str = DEFAULT_LLM_MODEL,
    update_page_id: str | None = None,
    force_scenario_id: str | None = None,
) -> dict[str, Any]:
    """End-to-end run. Returns a dict with all artifacts.

    Args:
        update_page_id: If set, update this existing Notion page instead of
            creating a new one (redo mode for failed scenarios).
        force_scenario_id: If set, use this scenario_id instead of auto-assigning.
    """
    if not reference_path.is_file():
        raise ValueError(f"reference image not found: {reference_path}")
    assets_root = assets_root or Path(DEFAULT_ASSETS_ROOT).expanduser()

    notion = NotionClient()

    # 1. Fetch existing scenarios for dedup context
    logger.info("kyoka_pipeline: fetching existing scenarios from Notion")
    existing = fetch_existing_scenarios(notion)
    logger.info("kyoka_pipeline: %d existing scenarios fetched", len(existing))
    if force_scenario_id:
        scenario_id = force_scenario_id
    else:
        scenario_id = next_scenario_id(existing)
    logger.info("kyoka_pipeline: assigning scenario_id=%s", scenario_id)

    # 2. Build prompts and call LLM
    system_prompt, user_message = build_full_prompts(
        theme=theme,
        season=season,
        title_hint=title_hint,
        existing_scenarios=existing,
        market_pulse=market_pulse,
    )

    if dry_run:
        return {
            "scenario_id": scenario_id,
            "system_prompt": system_prompt,
            "user_message": user_message,
            "existing_count": len(existing),
        }

    raw = call_claude_for_scenario(system_prompt, user_message, model=llm_model)
    spec = parse_llm_json(raw)

    # 3. Validate
    errors = validate_scenario_spec(spec)
    if errors:
        # Surface errors but continue if user passed --force; default abort.
        joined = "\n  - ".join(errors)
        raise RuntimeError(
            f"scenario spec validation failed:\n  - {joined}\n\n--- raw LLM output ---\n{raw[:1500]}"
        )

    # 4. Image generation — intentionally skipped in pipeline.
    # chisuke pastes the GPT Image Prompt from Notion into ChatGPT GUI manually.
    # kyoka_image.py is kept for future use but not called here.
    out_dir = assets_root / scenario_id
    image_result = {"note": "image generation skipped — use ChatGPT GUI with GPT Image Prompt from Notion"}

    # 5. Create or update Notion record
    notion_result = {}
    if not skip_notion:
        notes_extra = f"自動生成（kyoka_pipeline）｜LLM={llm_model}｜画像={out_dir}"
        if update_page_id:
            notion_result = update_notion_record(
                page_id=update_page_id,
                spec=spec,
                scenario_id=scenario_id,
                storyboard_filename=f"{scenario_id}/storyboard",
                notes_extra=notes_extra,
                client=notion,
            )
            logger.info("kyoka_pipeline: Notion page updated %s", notion_result)
        else:
            notion_result = create_notion_record(
                spec=spec,
                scenario_id=scenario_id,
                storyboard_filename=f"{scenario_id}/storyboard",
                notes_extra=notes_extra,
                client=notion,
            )
            logger.info("kyoka_pipeline: Notion page created %s", notion_result)

    return {
        "scenario_id": scenario_id,
        "spec": spec,
        "image_result": image_result,
        "notion_result": notion_result,
        "out_dir": str(out_dir),
    }


# ── Tool Schemas ────────────────────────────────────────────


def get_tool_schemas() -> list[dict]:
    return [
        {
            "name": "kyoka_pipeline_run",
            "description": "Generate a complete Kyoka scenario: spec via LLM → 6 frames → Notion record.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "theme": {"type": "string"},
                    "season": {"type": "string"},
                    "reference_path": {"type": "string"},
                    "title_hint": {"type": "string"},
                    "market_pulse": {"type": "string"},
                    "skip_images": {"type": "boolean", "default": False},
                    "skip_notion": {"type": "boolean", "default": False},
                },
                "required": ["theme", "season", "reference_path"],
            },
        },
    ]


# ── Dispatch ────────────────────────────────────────────────


def dispatch(name: str, args: dict[str, Any]) -> Any:
    args.pop("anima_dir", None)
    if name == "kyoka_pipeline_run":
        return run_pipeline(
            theme=args["theme"],
            season=args["season"],
            reference_path=Path(args["reference_path"]).expanduser(),
            title_hint=args.get("title_hint"),
            market_pulse=args.get("market_pulse"),
            skip_images=args.get("skip_images", False),
            skip_notion=args.get("skip_notion", False),
        )
    raise ValueError(f"Unknown tool: {name}")


# ── CLI ─────────────────────────────────────────────────────


def cli_main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Kyoka scenario pipeline (LLM→images→Notion)")
    parser.add_argument("--theme", required=True, help="Scenario theme (e.g. '梅雨の縁側・雨音')")
    parser.add_argument("--season", required=True,
                        choices=["early_spring", "late_spring", "early_summer", "midsummer", "autumn", "winter"])
    parser.add_argument("--reference", type=Path, default=Path(DEFAULT_REFERENCE).expanduser())
    parser.add_argument("--title-hint", default=None)
    parser.add_argument("--market-pulse", default=None, help="Optional market_pulse text from kiri")
    parser.add_argument("--assets-root", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true",
                        help="Print prompts and exit without calling LLM/images/Notion")
    parser.add_argument("--skip-images", action="store_true",
                        help="Generate spec + Notion record but skip image generation")
    parser.add_argument("--skip-notion", action="store_true",
                        help="Generate spec + images but skip Notion record")
    parser.add_argument("--llm-model", default=DEFAULT_LLM_MODEL)
    parser.add_argument("--save-spec", type=Path, default=None,
                        help="Write the LLM spec JSON to this path for inspection")
    parser.add_argument("--update-page-id", default=None,
                        help="Update an existing Notion page instead of creating new (redo mode)")
    parser.add_argument("--force-scenario-id", default=None,
                        help="Override auto-assigned scenario_id (e.g. kyoka_scenario_004)")
    args = parser.parse_args(argv)

    try:
        result = run_pipeline(
            theme=args.theme,
            season=args.season,
            reference_path=args.reference.expanduser(),
            title_hint=args.title_hint,
            market_pulse=args.market_pulse,
            assets_root=args.assets_root.expanduser() if args.assets_root else None,
            dry_run=args.dry_run,
            skip_images=args.skip_images,
            skip_notion=args.skip_notion,
            llm_model=args.llm_model,
            update_page_id=args.update_page_id,
            force_scenario_id=args.force_scenario_id,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.save_spec and "spec" in result:
        args.save_spec.parent.mkdir(parents=True, exist_ok=True)
        args.save_spec.write_text(
            json.dumps(result["spec"], ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"spec saved: {args.save_spec}")

    # Trim spec from console output to keep it readable
    summary = {k: v for k, v in result.items() if k != "spec"}
    if "spec" in result:
        summary["spec_title_jp"] = result["spec"].get("title_jp")
        summary["spec_season"] = result["spec"].get("season")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    cli_main()
