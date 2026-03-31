# AnimaWorks - Digital Anima Framework
# Copyright (C) 2026 AnimaWorks Authors
# SPDX-License-Identifier: Apache-2.0

"""TikTok carousel image generation tool for AnimaWorks.

Generates background images via fal.ai FLUX, then composites Japanese text
overlays using Pillow. Ported from ai-tiktok/automation/scripts/overlay_text.py.
Used by tama (TikTok制作担当).
"""
from __future__ import annotations

import json
import os
import re
import uuid
import urllib.request
from pathlib import Path
from typing import Any

from core.tools._base import logger

# ── Execution Profile ─────────────────────────────────────

EXECUTION_PROFILE: dict[str, dict[str, object]] = {
    "tiktok_generate_carousel_images": {"expected_seconds": 90, "background_eligible": True},
}

# ── Constants ─────────────────────────────────────────────

TEXT_TRIGGER_KEYWORDS = [
    "screen", "display", "monitor", "smartphone", "phone", "tablet",
    "computer", "laptop", "pc", "digital", "interface", "ui", "app",
    "brain", "neural", "hologram", "dashboard", "data", "code",
    "terminal", "software", "website", "browser", "keyboard",
]

NO_TEXT_NEGATIVES = (
    "text, letters, words, english, writing, typography, labels, captions, "
    "watermark, signature, subtitles, numbers, digits, characters, glyphs, "
    "inscription, font, lettering, readable text, UI text, screen text, "
    "extra limbs, extra legs, five legs, six legs, deformed, bad anatomy, "
    "mutated, malformed, disfigured"
)

FAL_MODEL = "fal-ai/flux/schnell"
IMAGE_SIZE = "portrait_16_9"  # 9:16 vertical for TikTok
NUM_INFERENCE_STEPS = 4

# ── Font fallback for emoji/special chars ─────────────────

_CHAR_FALLBACK_MAP = {
    '\u2714': '○', '\u2713': '○', '\u2197': '→', '\u2198': '→',
    '\u2B06': '↑', '\U0001F525': '★', '\U0001F4CC': '●',
    '\U0001F680': '★', '\U0001F4A1': '◆', '\U0001F4B0': '◆',
    '\U0001F31F': '★', '\U00002728': '★', '\U0001F44D': '○',
    '\U0001F4F1': '■', '\U0001F4BB': '■', '\U0001F447': '↓',
    '\U0001F446': '↑', '\U0001F4E4': '→', '\U0001F4E3': '●',
}


def _normalize_text(text: str) -> str:
    text = re.sub(r'[\uFE00-\uFE0F]', '', text)
    for src, dst in _CHAR_FALLBACK_MAP.items():
        text = text.replace(src, dst)
    return text


def _get_japanese_font(size: int = 60):
    from PIL import ImageFont
    paths = [
        "/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc",
        "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
        "/System/Library/Fonts/Hiragino Sans W6.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Bold.otf",
    ]
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except IOError:
                continue
    logger.warning("No Japanese font found, using default")
    return ImageFont.load_default()


# ── Text wrapping with Japanese line-break rules ──────────

def _wrap_text(text: str, font, max_width: int) -> list[str]:
    """Smart text wrapping with Japanese kinzoku (line-break) rules."""
    atoms = re.findall(
        r'[「『（【《][^」』）】》]*[」』）】》]'
        r'|→[^\s]+'
        r'|[A-Za-z0-9][A-Za-z0-9\-\.]*'
        r'|[ァ-ンヴー]+'
        r'| +'
        r'|[^\s]',
        text
    )
    BREAK_AFTER = set('はがをにでもとやかへのよりから。、！？…・ ')
    NO_LINE_START = set('」』）】》、。！？…ー')
    NO_LINE_END = set('「『（【《')

    result = []
    current = ""
    for atom in atoms:
        if atom.strip() == '':
            current += atom
            continue
        test = current + atom
        b = font.getbbox(test)
        if (b[2] - b[0]) > max_width and current:
            break_idx = -1
            for i in range(len(current) - 1, max(len(current) - 10, -1), -1):
                if current[i] in BREAK_AFTER:
                    candidate = i + 1
                    next_char = current[candidate] if candidate < len(current) else atom[0] if atom else ''
                    if next_char in NO_LINE_START:
                        continue
                    if current[i] in NO_LINE_END:
                        continue
                    break_idx = candidate
                    break
            if break_idx > 0:
                result.append(current[:break_idx].rstrip())
                current = current[break_idx:].lstrip() + atom
            else:
                if atom and atom[0] in NO_LINE_START:
                    current += atom
                    continue
                result.append(current.rstrip())
                current = atom
        else:
            current = test
    if current:
        result.append(current)
    return result if result else [text]


# ── Text overlay rendering ────────────────────────────────

def _draw_text_overlay(text: str, font, img_w: int, img_h: int, vertical: str = "center"):
    """Draw centered text with semi-transparent dark background."""
    from PIL import Image, ImageDraw

    max_text_w = int(img_w * 0.85)
    raw_lines = text.split('\\n') if '\\n' in text else text.split('\n')

    lines = []
    for raw in raw_lines:
        if not raw.strip():
            lines.append("")
            continue
        bbox = font.getbbox(raw)
        if (bbox[2] - bbox[0]) <= max_text_w:
            lines.append(raw)
        else:
            lines.extend(_wrap_text(raw, font, max_text_w))

    line_spacing = 20
    line_dims = []
    max_line_w = 0
    total_h = 0
    for line in lines:
        bbox = font.getbbox(line) if line else (0, 0, 0, font.size)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1] if line else font.size
        line_dims.append((w, h))
        max_line_w = max(max_line_w, w)
        total_h += h + line_spacing
    total_h -= line_spacing

    pad_x, pad_y = 50, 50
    box_w = max_line_w + pad_x * 2
    box_h = total_h + pad_y * 2
    box_x1 = (img_w - box_w) // 2
    box_y1 = int(img_h * 0.08) if vertical == "upper" else (img_h - box_h) // 2
    box_x2 = box_x1 + box_w
    box_y2 = box_y1 + box_h

    overlay = Image.new('RGBA', (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    r = 30
    fill = (0, 0, 0, 190)
    draw.rectangle([box_x1 + r, box_y1, box_x2 - r, box_y2], fill=fill)
    draw.rectangle([box_x1, box_y1 + r, box_x2, box_y2 - r], fill=fill)
    draw.pieslice([box_x1, box_y1, box_x1 + r * 2, box_y1 + r * 2], 180, 270, fill=fill)
    draw.pieslice([box_x2 - r * 2, box_y1, box_x2, box_y1 + r * 2], 270, 360, fill=fill)
    draw.pieslice([box_x1, box_y2 - r * 2, box_x1 + r * 2, box_y2], 90, 180, fill=fill)
    draw.pieslice([box_x2 - r * 2, box_y2 - r * 2, box_x2, box_y2], 0, 90, fill=fill)

    cur_y = box_y1 + pad_y
    for i, line in enumerate(lines):
        w, h = line_dims[i]
        if not line:
            cur_y += h + line_spacing
            continue
        line_x = (img_w - w) // 2
        bbox = font.getbbox(line)
        off_y = bbox[1]
        draw.text((line_x + 4, cur_y - off_y + 4), line, font=font, fill=(0, 0, 0, 255))
        draw.text((line_x, cur_y - off_y), line, font=font, fill=(255, 255, 255, 255))
        cur_y += h + line_spacing

    return overlay


def _composite_text_on_image(image_path: str, overlay_text: str, slide_index: int) -> bool:
    """Composite overlay text onto an existing image file."""
    from PIL import Image

    try:
        font = _get_japanese_font(size=60)
        text = _normalize_text(overlay_text)

        with Image.open(image_path) as img:
            img = img.convert("RGBA")
            vertical = "upper" if slide_index == 0 else "center"
            overlay = _draw_text_overlay(text, font, img.width, img.height, vertical=vertical)
            final = Image.alpha_composite(img, overlay).convert("RGB")
            final.save(image_path, "PNG")

        logger.info("Text composited on slide %d: %s", slide_index + 1, image_path)
        return True
    except Exception as e:
        logger.error("Text composite failed for slide %d: %s", slide_index + 1, e)
        return False


# ── Tool Schemas ──────────────────────────────────────────


def get_tool_schemas() -> list[dict]:
    return [
        {
            "name": "tiktok_generate_carousel_images",
            "description": (
                "TikTokカルーセル用の画像を5枚生成する。"
                "fal.ai FLUXで背景画像を生成し、Pillowでoverlay_textを合成する。"
                "9:16縦型。完成画像がそのまま投稿素材になる。"
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "prompts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "5枚分の背景画像プロンプト（英語、テキスト指示を含まないこと）",
                    },
                    "overlay_texts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "5枚分のoverlay_text（日本語、\\nで改行）",
                    },
                    "draft_id": {
                        "type": "string",
                        "description": "関連するドラフトのファイル名（例: draft_20260331_evening.json）",
                    },
                },
                "required": ["prompts", "overlay_texts"],
            },
        },
    ]


# ── Image Generation ──────────────────────────────────────


def _generate_single(prompt: str, output_dir: Path, index: int) -> dict:
    try:
        import fal_client
    except ImportError:
        return {"success": False, "error": "fal-client not installed"}

    neg = NO_TEXT_NEGATIVES
    arguments = {
        "prompt": prompt,
        "image_size": IMAGE_SIZE,
        "num_inference_steps": NUM_INFERENCE_STEPS,
        "num_images": 1,
        "enable_safety_checker": True,
        "negative_prompt": neg,
    }

    try:
        result = fal_client.run(FAL_MODEL, arguments=arguments)
        images = result.get("images", [])
        if not images:
            return {"success": False, "error": f"No images for slide {index + 1}"}

        url = images[0].get("url", "")
        ext = url.split("?")[0].rsplit(".", 1)[-1] or "png"
        filename = f"slide_{index + 1}_{uuid.uuid4().hex[:6]}.{ext}"
        filepath = output_dir / filename
        urllib.request.urlretrieve(url, str(filepath))
        return {"success": True, "path": str(filepath), "slide": index + 1}
    except Exception as e:
        logger.error("Image generation failed for slide %d: %s", index + 1, e)
        return {"success": False, "error": str(e), "slide": index + 1}


def generate_carousel_images(
    prompts: list[str],
    overlay_texts: list[str] | None = None,
    draft_id: str | None = None,
    anima_dir: str | None = None,
) -> dict:
    """Generate 5 carousel images with text overlay."""
    if len(prompts) != 5:
        return {"success": False, "error": f"5枚のプロンプトが必要です（{len(prompts)}枚指定）"}

    if overlay_texts and len(overlay_texts) != 5:
        return {"success": False, "error": f"overlay_textsも5枚必要です（{len(overlay_texts)}枚指定）"}

    # Validate: no text instructions in prompts
    text_indicators = ["text", "word", "letter", "caption", "title", "テキスト", "文字"]
    for i, p in enumerate(prompts):
        if any(ind in p.lower() for ind in text_indicators):
            return {
                "success": False,
                "error": f"スライド{i+1}のプロンプトにテキスト指示あり。背景のみにしてください。",
            }

    from core.paths import get_data_dir
    output_dir = get_data_dir() / "tiktok_images"
    if draft_id:
        output_dir = output_dir / draft_id.replace(".json", "")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Generate background images
    results = []
    paths = []
    for i, prompt in enumerate(prompts):
        result = _generate_single(prompt, output_dir, i)
        results.append(result)
        if result.get("success"):
            paths.append(result["path"])

    gen_count = sum(1 for r in results if r.get("success"))

    # Step 2: Composite text overlays
    text_count = 0
    if overlay_texts and gen_count == 5:
        for i, (path, text) in enumerate(zip(paths, overlay_texts)):
            if _composite_text_on_image(path, text, i):
                text_count += 1

    return {
        "success": gen_count == 5,
        "message": f"画像生成{gen_count}/5枚、テキスト合成{text_count}/5枚",
        "output_dir": str(output_dir),
        "paths": paths,
        "results": results,
    }


# ── Dispatch ──────────────────────────────────────────────


def dispatch(name: str, args: dict[str, Any]) -> Any:
    anima_dir = args.pop("anima_dir", None)

    if name == "tiktok_generate_carousel_images":
        return generate_carousel_images(
            prompts=args["prompts"],
            overlay_texts=args.get("overlay_texts"),
            draft_id=args.get("draft_id"),
            anima_dir=anima_dir,
        )

    raise ValueError(f"Unknown tool: {name}")
