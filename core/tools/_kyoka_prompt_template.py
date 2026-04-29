# AnimaWorks - Digital Anima Framework
# Copyright (C) 2026 AnimaWorks Authors
# SPDX-License-Identifier: Apache-2.0

"""Kyoka prompt-template builder for scenario generation.

Holds the FIXED character / world spec extracted from scenario_001-003
in the Kyoka Scenarios Notion DB, and builds the system + user prompts
fed to claude-sonnet-4-6 when sumi (or the CLI) needs to invent a new
scenario.

Why a Python module (not JSON):
- The "existing scenarios to avoid" list is fetched live from Notion at
  runtime; embedding it as Python lets the caller pass a list[dict]
  directly instead of round-tripping through a JSON file.

Source of truth for the fixed spec:
- ~/.animaworks/common_knowledge/tiktok_templates/kyoka/asset_pool.json
- Notion DB Kyoka Scenarios (f1d407fcb3d94ca78cd81ddbe2c11d67)
  scenario_001/002/003 GPT Image Prompt の冒頭ブロック
"""
from __future__ import annotations

import json
import re
import textwrap
from typing import Any

# ── Fixed character spec (DO NOT vary across scenarios) ───────────

KYOKA_FIXED_CHARACTER_SPEC = textwrap.dedent("""\
    Character: 鏡花 (Kyoka) — a refined, aristocratic Japanese woman of mysterious presence.

    APPEARANCE (immutable across all scenarios — match the uploaded reference image exactly):
    - Age: late twenties — preserve the youthful firmness, sharp jawline, and crisp facial structure of the reference image exactly. Do NOT round the face, do NOT soften the jaw, do NOT age the subject.
    - Face structure: sharp defined jawline, prominent cheekbones, taut clear skin — identical to the reference image
    - Hair: long black hair, tied low at the nape, glossy and well-kept
    - Hair accessories: exactly two red kanzashi hairpins on the right side of her head; one of the kanzashi is decorated with a single red chrysanthemum flower; no other hair ornaments
    - Costume: traditional black silk kimono with elegant gold peony embroidery (high-quality formal kimono, NOT humble or worn), obi sash neatly tied at her back
    - Skin: pale, fine, porcelain-smooth skin
    - Build: slender, upright, dignified bearing

    EXPRESSION (immutable across all scenarios):
    - Refined, regal, composed, dignified — the bearing of a noblewoman
    - Quiet intensity, subtle inner stillness, contemplative
    - Lips relaxed and softly closed (not pressed, not pursed, no smile, no smirk)
    - Eyes calm and observant (NOT glaring, NOT scowling); the gaze carries gravity, not hostility
    - SMOOTH, RELAXED FOREHEAD AND BROW — absolutely NO furrowed brow, NO knit eyebrows, NO frown lines, NO tension between the eyes
    - Never angry, never grim, never sour; never "town girl", never coy, never giggling
    - Cool elegance, classical Japanese aesthetic — think 平安貴族 / 能の女面 / 上臈 (court lady), refined and remote

    OVERALL ATMOSPHERE around the character:
    - Settings should feel high-class, elegant, well-maintained — NOT shabby, NOT damp-poor, NOT rustic-peasant
    - Even in nature scenes, the framing favors refinement (well-kept gardens, lacquered architecture, polished wood) over rural roughness
""")

# ── Mandatory blocks (must appear verbatim in GPT Image Prompt) ────

MANDATORY_HEADER = textwrap.dedent("""\
    ⚠️⚠️⚠️ MANDATORY IMAGE GENERATION MODE ⚠️⚠️⚠️
    You MUST generate an actual image file as output. Do NOT respond with text, specifications, descriptions, shot lists, or any written breakdown.
    Do NOT explain what you cannot do.
    Do NOT offer alternative formats.
    Invoke your image generation tool (DALL-E / GPT Image / native image generator) immediately and produce ONE image file.
    The ONLY acceptable output is a rendered PNG/JPG image. If you cannot generate an image, respond with exactly this single line: "IMAGE_GENERATION_UNAVAILABLE" — nothing else.
    ═══════════════════════════════════════════

    [Reference image uploaded: portrait of a Japanese woman named Kyoka]
""")

MANDATORY_FACE_CONSISTENCY = textwrap.dedent("""\
    ═══════════════════════════════════════════
    CRITICAL — FACE CONSISTENCY
    ═══════════════════════════════════════════
    - Every frame MUST feature the identical face as the reference image
    - Preserve exact facial features, hairstyle (long black hair tied low at nape, two red kanzashi hairpins on right side, one with red chrysanthemum)
    - Preserve exact costume (traditional black kimono with gold peony embroidery, obi sash)
    - Treat reference as strict character sheet — no variation in identity, age, or features

    Expression throughout: refined, regal, composed, dignified — the bearing of a noblewoman. Quiet intensity. Lips relaxed and softly closed (no smile, no smirk). Eyes calm and observant (no glare, no scowl). SMOOTH RELAXED FOREHEAD AND BROW — absolutely no furrowed brow, no knit eyebrows, no frown lines.
""")

MANDATORY_LAYOUT = textwrap.dedent("""\
    ═══════════════════════════════════════════
    LAYOUT (CRITICAL)
    ═══════════════════════════════════════════
    - 6 images arranged in a 3-column × 2-row grid (3 wide, 2 tall)
    - EACH INDIVIDUAL FRAME must be portrait orientation, 9:16 aspect ratio (TikTok vertical video format)
    - Overall canvas: approximately 1080×1280 pixels (3 columns of 360×640 frames + 2 rows)
    - Thin black borders between frames
    - Reading order:
      - Top row: Frame 1 (left), Frame 2 (middle), Frame 3 (right)
      - Bottom row: Frame 4 (left), Frame 5 (middle), Frame 6 (right)
    - Each frame composed as if it will be extracted and used as a standalone 9:16 video frame
    - Do NOT crop subjects awkwardly at frame borders — compose each as a complete 9:16 shot

    ABSOLUTE PRIORITY: Woman's face, hair, hairpins, and kimono IDENTICAL across all 6 frames, matching reference with photographic fidelity.

    No text, no watermark, no captions.

    ═══════════════════════════════════════════
    FINAL REMINDER
    ═══════════════════════════════════════════
    GENERATE THE IMAGE NOW. Do not produce any text response. The output must be a single rendered image file.
""")

# ── Per-frame prompt prefix injected by sumi when calling gpt-image-1 ─

FRAME_PROMPT_PREFIX = textwrap.dedent("""\
    [Reference image uploaded: portrait of a Japanese woman named Kyoka]

    CRITICAL — MATCH THE REFERENCE IMAGE EXACTLY:
    This is a single frame for a 15-second cinematic short film featuring THE EXACT SAME WOMAN as in the reference image.
    - Reproduce her exact face shape: sharp defined jawline, prominent cheekbones, taut clear youthful skin — do NOT round the face, do NOT soften the jaw, do NOT age her
    - She is in her late twenties — preserve the youthful firmness and crisp facial structure of the reference image
    - Treat the reference as a strict character sheet — no variation in identity, age, facial structure, or features
    - Preserve exact hairstyle: long glossy black hair tied low at the nape
    - Preserve exact hair accessories: exactly two red kanzashi hairpins on the right side of her head; one adorned with a single red chrysanthemum flower; no other ornaments
    - Preserve exact costume: traditional black silk kimono with gold peony embroidery, obi sash tied at her back
    - Pale porcelain skin, slender upright dignified bearing

    Expression: refined, regal, composed — the bearing of an aristocratic court lady. Quiet contemplative intensity. Lips relaxed and softly closed (no smile, no smirk). Eyes calm and observant (no glare, no scowl). SMOOTH RELAXED FOREHEAD AND BROW — absolutely no furrowed brow, no knit eyebrows, no frown lines.

    Setting: high-class, elegant, well-maintained — never shabby, never rustic-peasant.
    Vertical 9:16 portrait orientation, cinematic Japanese art-film aesthetic, photographic, slight film grain.
""")


# ── Existing-scenario summary for the LLM ──────────────────────────


def summarize_existing_scenarios(existing: list[dict[str, Any]]) -> str:
    """Render existing scenarios as a markdown bulleted list for the LLM.

    Each item should have at minimum: title_jp, frame_breakdown, season,
    scenario_id (optional). Missing fields are skipped gracefully.
    """
    if not existing:
        return "(no existing scenarios)"

    lines: list[str] = []
    for s in existing:
        title = s.get("title_jp") or s.get("Title (JP)") or s.get("title") or "?"
        sid = s.get("scenario_id") or s.get("Scenario ID") or ""
        season = s.get("season") or s.get("Season") or ""
        breakdown = s.get("frame_breakdown") or s.get("Frame Breakdown") or ""
        # Compress breakdown to single line
        breakdown_compact = " / ".join(p.strip() for p in breakdown.replace("<br>", "\n").splitlines() if p.strip())
        lines.append(
            f"- **{title}** ({sid} · {season}) → {breakdown_compact[:280]}"
        )
    return "\n".join(lines)


# ── System / user prompt builders ──────────────────────────────────


def build_system_prompt() -> str:
    """The system prompt for claude-sonnet-4-6 when generating a new scenario."""
    return textwrap.dedent(f"""\
        あなたは Kyoka 事業部のシナリオ設計者です。AIキャラクター「鏡花（Kyoka）」のTikTok向け15秒動画用の6フレーム絵コンテを設計します。

        ## 絶対不変の前提（破ったら却下）

        {KYOKA_FIXED_CHARACTER_SPEC}

        ## 出力ルール

        - 出力は **JSONのみ**。前後に何も書かない。コードフェンスも不要。
        - 全フィールド埋める。空欄禁止。
        - キャラクター記述（衣装・髪・髪飾り・表情）は必ず frame_prompts と gpt_image_prompt の両方に明示する
        - 「町娘」「浴衣」「微笑み」「surprised」「giggling」「coy」「playful」等の俗っぽい語は使わない
        - 「fierce」「piercing」「intense」「scowl」「glare」「frown」「furrowed brow」「knit eyebrows」等の **怒り・眉間ジワを連想させる語は禁止**（過去シナリオで貧相・怒り顔の出力を生んだ）
        - 「shabby」「ramshackle」「rustic」「humble」「weathered」等の **貧相・荒れた世界観の語は禁止**（鏡花は貴族的な気品を持つキャラクター）
        - 代わりに使うべき表現: regal, refined, composed, dignified, aristocratic, court lady, noblewoman, quiet contemplative intensity, smooth relaxed brow, calm observant gaze, classical elegance
        - 既出シナリオの構図・テーマを真似ない（差別化必須）

        ## 出力スキーマ

        {{
          "title_jp": "鏡花、〜",
          "scenario_id_suggestion": "kyoka_scenario_NNN（次の番号）",
          "season": "early_spring|late_spring|early_summer|midsummer|autumn|winter",
          "duration_sec": 15,
          "frame_count": 6,
          "frame_breakdown": "1 (0:00-2.5s) ... <br>2 (2.5-5.0s) ... <br>3 ... <br>4 ... <br>5 ... <br>6 ...",
          "frame_prompts": [
            "Frame 1 用の単独プロンプト（FRAME_PROMPT_PREFIX に続く形で書く・1024x1536 縦の単独画像として完結する記述）",
            "Frame 2 用",
            "Frame 3 用",
            "Frame 4 用",
            "Frame 5 用",
            "Frame 6 用"
          ],
          "gpt_image_prompt": "既存003と同じ構造の完全プロンプト（MANDATORY HEADER → CRITICAL FACE CONSISTENCY → STORYBOARD 6 FRAMES → VISUAL STYLE → LAYOUT → FINAL REMINDER）。絵コンテ全体を1枚生成するときに使う。",
          "seedance_prompt": "既存003と同じ構造の完全プロンプト（<<<image_1>>> 注意書き含む）。chisuke が Seedance Web で動画化するときに貼る。",
          "tiktok_caption": "She walks where ... の英語フック1行 + 日本語キーワード短い英訳 + Follow @kyokakisaragi ✨ + 固定タグ群",
          "instagram_caption": "TikTokよりやや詳しめ・固定タグ + 追加タグで20個以上",
          "bgm_notes": "和楽器中心の選曲メモ。シーン6はクライマックスにせず余韻で締める指示を含む。",
          "color_grading": "色調メモ",
          "lighting_progression": "Frame 1〜6 の光の進行",
          "emotion_arc": "Frame 1〜6 の感情アーク",
          "differentiation_note": "既出シナリオとどう差別化したかの1〜2行説明（chisuke レビュー用）"
        }}
    """)


def build_user_message(
    theme: str,
    season: str,
    title_hint: str | None,
    existing_scenarios: list[dict[str, Any]],
    market_pulse: str | None = None,
) -> str:
    """The user message that puts the actual request in context."""
    existing_block = summarize_existing_scenarios(existing_scenarios)
    market_block = (
        f"\n## 市場パルス（kiriから・参考）\n{market_pulse}\n"
        if market_pulse
        else ""
    )
    title_line = f"\n- タイトル案: 「{title_hint}」（参考・LLMが微調整可）" if title_hint else ""

    return textwrap.dedent(f"""\
        ## 今回のお題

        - テーマ: {theme}
        - 季節: {season}{title_line}

        ## 既出シナリオ（被らないこと）

        {existing_block}
        {market_block}
        ## 出力

        上記制約のもとで JSON のみを出力してください。
    """)


def build_full_prompts(
    theme: str,
    season: str,
    title_hint: str | None,
    existing_scenarios: list[dict[str, Any]],
    market_pulse: str | None = None,
) -> tuple[str, str]:
    """Return (system_prompt, user_message) ready for claude-sonnet-4-6."""
    return build_system_prompt(), build_user_message(
        theme=theme,
        season=season,
        title_hint=title_hint,
        existing_scenarios=existing_scenarios,
        market_pulse=market_pulse,
    )


# ── Validator (used by kyoka_pipeline before image generation) ─────


REQUIRED_KEYS = (
    "title_jp", "season", "duration_sec", "frame_count", "frame_breakdown",
    "frame_prompts", "gpt_image_prompt", "seedance_prompt",
    "tiktok_caption", "instagram_caption", "bgm_notes",
)
# Use word-boundary regex match (so "smile" does NOT match "unsmiling").
FORBIDDEN_TERMS = (
    # casual/peasant world
    "町娘", "浴衣", "yukata", "smiling", "smile", "smiles", "giggle", "giggling",
    "coy", "playful", "town girl",
    # angry / brow-tension world — only outright positive assertions, not negations
    # (LLM often writes "no furrowed brow" which is correct; we skip those words)
    "fierce", "fiercely", "angry", "grim",
    # shabby / damp-poor world
    "shabby", "ramshackle", "ragged",
)
# Required somewhere in the spec (not necessarily every single frame_prompt
# — a tight detail-shot may not mention "kanzashi"). We assert presence at
# the spec level instead.
REQUIRED_TERMS_IN_SPEC = (
    "black",  # kimono
    "kanzashi",
    "regal",
)


def _has_word(haystack: str, needle: str) -> bool:
    """Whole-word match (case-insensitive) for ASCII needles; substring for non-ASCII."""
    if needle.isascii():
        return re.search(rf"\b{re.escape(needle)}\b", haystack, flags=re.IGNORECASE) is not None
    return needle in haystack


def validate_scenario_spec(spec: dict[str, Any]) -> list[str]:
    """Return a list of validation errors. Empty list = pass."""
    errors: list[str] = []

    for k in REQUIRED_KEYS:
        if k not in spec or spec[k] in (None, "", [], {}):
            errors.append(f"missing required field: {k}")

    frames = spec.get("frame_prompts")
    if isinstance(frames, list):
        if len(frames) != 6:
            errors.append(f"frame_prompts must have 6 entries, got {len(frames)}")
        for i, fp in enumerate(frames, start=1):
            if not isinstance(fp, str) or len(fp) < 50:
                errors.append(f"frame_prompts[{i}] too short or not a string")
                continue
            for term in FORBIDDEN_TERMS:
                if _has_word(fp, term):
                    errors.append(f"frame_prompts[{i}] contains forbidden term: {term!r}")
    else:
        errors.append("frame_prompts must be a list")

    # Spec-level required-term check (over the whole gpt_image_prompt + frame_prompts joined)
    haystack_blob = (spec.get("gpt_image_prompt") or "") + "\n" + "\n".join(frames or [])
    for term in REQUIRED_TERMS_IN_SPEC:
        if not _has_word(haystack_blob, term):
            errors.append(f"spec missing required term anywhere: {term!r}")

    # Sanity check on captions / prompts
    for k in ("gpt_image_prompt", "seedance_prompt"):
        v = spec.get(k, "")
        if isinstance(v, str) and len(v) < 200:
            errors.append(f"{k} suspiciously short ({len(v)} chars)")

    if isinstance(spec.get("tiktok_caption"), str):
        if "@kyokakisaragi" not in spec["tiktok_caption"]:
            errors.append("tiktok_caption missing @kyokakisaragi handle")

    return errors


def parse_llm_json(raw: str) -> dict[str, Any]:
    """Tolerate a markdown code fence around the JSON output."""
    text = raw.strip()
    if text.startswith("```"):
        # strip leading fence + optional language id
        lines = text.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return json.loads(text)
