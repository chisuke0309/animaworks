# AnimaWorks - Digital Anima Framework
# Copyright (C) 2026 AnimaWorks Authors
# SPDX-License-Identifier: Apache-2.0

"""Kyoka 6-frame storyboard image generator (gpt-image-1 reference-based).

Wraps OpenAI Images Edits API with input_fidelity=high so the same Kyoka
face is preserved across all 6 frames. Used by sumi (Kyoka 制作担当) to
turn LLM-generated per-frame prompts into a finished storyboard.

Pipeline (1 scenario):
  1. For each of 6 prompts, POST /v1/images/edits with the reference image.
  2. Save each frame as PNG under {out_dir}/frame{NN}.png.
  3. Combine 6 frames into a 3x2 storyboard.png (matches existing
     kyoka_scenario_003_board.png layout).
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

from core.tools._base import get_credential, logger

# ── Constants ─────────────────────────────────────────────

OPENAI_EDITS_URL = "https://api.openai.com/v1/images/edits"
DEFAULT_MODEL = "gpt-image-1"
ALLOWED_SIZES = ("1024x1024", "1024x1536", "1536x1024")
ALLOWED_QUALITIES = ("high", "medium", "low")
ALLOWED_FIDELITIES = ("high", "low")

# ── Execution Profile ─────────────────────────────────────

EXECUTION_PROFILE: dict[str, dict[str, object]] = {
    "kyoka_image_generate": {"expected_seconds": 60, "background_eligible": True},
    "kyoka_image_storyboard": {"expected_seconds": 360, "background_eligible": True},
}


# ── Single-frame generation ────────────────────────────────


def generate_frame(
    reference_path: Path,
    prompt: str,
    out_path: Path,
    size: str = "1024x1536",
    quality: str = "high",
    input_fidelity: str = "high",
    model: str = DEFAULT_MODEL,
    timeout: float = 240.0,
) -> Path:
    """Generate a single frame via /v1/images/edits.

    Args:
        reference_path: JPG/PNG/WebP file pinning Kyoka's face.
        prompt: Per-frame text prompt (already includes character spec).
        out_path: Where to save the resulting PNG.
        size: One of ALLOWED_SIZES.
        quality: One of ALLOWED_QUALITIES.
        input_fidelity: "high" preserves face features more strictly.
        model: gpt-image-1 (the only model that supports input_fidelity).
        timeout: HTTP timeout in seconds.

    Returns:
        out_path on success.

    Raises:
        ValueError: invalid size / quality / fidelity / missing reference.
        RuntimeError: API failure.
    """
    if size not in ALLOWED_SIZES:
        raise ValueError(f"size must be one of {ALLOWED_SIZES}, got {size}")
    if quality not in ALLOWED_QUALITIES:
        raise ValueError(f"quality must be one of {ALLOWED_QUALITIES}, got {quality}")
    if input_fidelity not in ALLOWED_FIDELITIES:
        raise ValueError(f"input_fidelity must be one of {ALLOWED_FIDELITIES}")
    if not reference_path.is_file():
        raise ValueError(f"reference image not found: {reference_path}")

    api_key = get_credential(
        credential_name="openai",
        tool_name="kyoka_image",
        env_var="OPENAI_API_KEY",
    )
    headers = {"Authorization": f"Bearer {api_key}"}

    suffix = reference_path.suffix.lower()
    mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png" if suffix == ".png" else "image/webp"
    files = [
        ("image[]", (reference_path.name, reference_path.read_bytes(), mime)),
    ]
    data = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "quality": quality,
        "input_fidelity": input_fidelity,
        "n": "1",
    }

    logger.info(
        "kyoka_image: edits ref=%s size=%s quality=%s fidelity=%s",
        reference_path.name, size, quality, input_fidelity,
    )
    t0 = time.time()
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(OPENAI_EDITS_URL, headers=headers, data=data, files=files)
    elapsed = time.time() - t0

    if resp.status_code != 200:
        raise RuntimeError(
            f"OpenAI Images edits failed (status={resp.status_code}, elapsed={elapsed:.1f}s): "
            f"{resp.text[:500]}"
        )

    payload = resp.json()
    items = payload.get("data") or []
    if not items or not items[0].get("b64_json"):
        raise RuntimeError(f"No b64_json in response: {str(payload)[:500]}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(base64.b64decode(items[0]["b64_json"]))
    logger.info(
        "kyoka_image: saved %s (%.1fs, %d bytes)",
        out_path, elapsed, out_path.stat().st_size,
    )
    return out_path


# ── Storyboard composition ──────────────────────────────────


def generate_storyboard(frame_paths: list[Path], out_path: Path) -> Path:
    """Combine 6 frames into a 3x2 storyboard PNG (matches existing 003 layout)."""
    if len(frame_paths) != 6:
        raise ValueError(f"expected 6 frames, got {len(frame_paths)}")

    images = [Image.open(p) for p in frame_paths]
    w, h = images[0].size
    images = [img.resize((w, h)) for img in images]

    cols, rows = 3, 2
    canvas = Image.new("RGB", (w * cols, h * rows), (0, 0, 0))
    for idx, img in enumerate(images):
        r, c = divmod(idx, cols)
        canvas.paste(img, (c * w, r * h))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, "PNG", optimize=True)
    logger.info("kyoka_image: storyboard saved %s", out_path)
    return out_path


# ── 6-frame batch (single scenario) ─────────────────────────


def generate_six_frames(
    reference_path: Path,
    prompts: list[str],
    out_dir: Path,
    size: str = "1024x1536",
    quality: str = "high",
    input_fidelity: str = "high",
) -> dict[str, Any]:
    """Generate all 6 frames + storyboard for one scenario.

    Returns dict with keys: frame_paths (list[str]), storyboard_path (str).
    """
    if len(prompts) != 6:
        raise ValueError(f"expected 6 prompts, got {len(prompts)}")
    out_dir.mkdir(parents=True, exist_ok=True)

    frame_paths: list[Path] = []
    for i, prompt in enumerate(prompts, start=1):
        out = out_dir / f"frame{i:02d}.png"
        generate_frame(
            reference_path=reference_path,
            prompt=prompt,
            out_path=out,
            size=size,
            quality=quality,
            input_fidelity=input_fidelity,
        )
        frame_paths.append(out)

    storyboard = out_dir / "storyboard.png"
    generate_storyboard(frame_paths, storyboard)

    return {
        "frame_paths": [str(p) for p in frame_paths],
        "storyboard_path": str(storyboard),
    }


# ── Tool Schemas ───────────────────────────────────────────


def get_tool_schemas() -> list[dict]:
    return [
        {
            "name": "kyoka_image_generate",
            "description": "Generate a single image frame for Kyoka via gpt-image-1 with a reference image.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "reference_path": {"type": "string", "description": "Path to face-anchor reference image"},
                    "prompt": {"type": "string"},
                    "out_path": {"type": "string"},
                    "size": {"type": "string", "enum": list(ALLOWED_SIZES), "default": "1024x1536"},
                    "quality": {"type": "string", "enum": list(ALLOWED_QUALITIES), "default": "high"},
                    "input_fidelity": {"type": "string", "enum": list(ALLOWED_FIDELITIES), "default": "high"},
                },
                "required": ["reference_path", "prompt", "out_path"],
            },
        },
        {
            "name": "kyoka_image_storyboard",
            "description": "Generate 6 frames + 3x2 storyboard for one Kyoka scenario.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "reference_path": {"type": "string"},
                    "prompts": {"type": "array", "items": {"type": "string"}, "minItems": 6, "maxItems": 6},
                    "out_dir": {"type": "string"},
                    "size": {"type": "string", "enum": list(ALLOWED_SIZES), "default": "1024x1536"},
                    "quality": {"type": "string", "enum": list(ALLOWED_QUALITIES), "default": "high"},
                    "input_fidelity": {"type": "string", "enum": list(ALLOWED_FIDELITIES), "default": "high"},
                },
                "required": ["reference_path", "prompts", "out_dir"],
            },
        },
    ]


# ── Dispatch ───────────────────────────────────────────────


def dispatch(name: str, args: dict[str, Any]) -> Any:
    args.pop("anima_dir", None)
    if name == "kyoka_image_generate":
        return {
            "out_path": str(generate_frame(
                reference_path=Path(args["reference_path"]).expanduser(),
                prompt=args["prompt"],
                out_path=Path(args["out_path"]).expanduser(),
                size=args.get("size", "1024x1536"),
                quality=args.get("quality", "high"),
                input_fidelity=args.get("input_fidelity", "high"),
            ))
        }
    if name == "kyoka_image_storyboard":
        return generate_six_frames(
            reference_path=Path(args["reference_path"]).expanduser(),
            prompts=args["prompts"],
            out_dir=Path(args["out_dir"]).expanduser(),
            size=args.get("size", "1024x1536"),
            quality=args.get("quality", "high"),
            input_fidelity=args.get("input_fidelity", "high"),
        )
    raise ValueError(f"Unknown tool: {name}")


# ── CLI ────────────────────────────────────────────────────


def cli_main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Kyoka image generation tool (gpt-image-1)")
    sub = parser.add_subparsers(dest="command", required=True)

    one = sub.add_parser("frame", help="Generate one frame")
    one.add_argument("--reference", required=True, type=Path)
    one.add_argument("--prompt", required=True)
    one.add_argument("--out", required=True, type=Path)
    one.add_argument("--size", default="1024x1536", choices=ALLOWED_SIZES)
    one.add_argument("--quality", default="high", choices=ALLOWED_QUALITIES)
    one.add_argument("--input-fidelity", default="high", choices=ALLOWED_FIDELITIES)

    six = sub.add_parser("storyboard", help="Generate 6 frames + storyboard")
    six.add_argument("--reference", required=True, type=Path)
    six.add_argument("--prompts-file", required=True, type=Path,
                     help='JSON file: {"prompts": [str×6]}')
    six.add_argument("--out-dir", required=True, type=Path)
    six.add_argument("--size", default="1024x1536", choices=ALLOWED_SIZES)
    six.add_argument("--quality", default="high", choices=ALLOWED_QUALITIES)
    six.add_argument("--input-fidelity", default="high", choices=ALLOWED_FIDELITIES)

    args = parser.parse_args(argv)

    try:
        if args.command == "frame":
            out = generate_frame(
                reference_path=args.reference.expanduser(),
                prompt=args.prompt,
                out_path=args.out.expanduser(),
                size=args.size,
                quality=args.quality,
                input_fidelity=args.input_fidelity,
            )
            print(f"OK: {out}")
        elif args.command == "storyboard":
            spec = json.loads(args.prompts_file.read_text(encoding="utf-8"))
            prompts = spec.get("prompts")
            if not isinstance(prompts, list) or len(prompts) != 6:
                raise ValueError("prompts-file must have 'prompts' = list of 6 strings")
            result = generate_six_frames(
                reference_path=args.reference.expanduser(),
                prompts=prompts,
                out_dir=args.out_dir.expanduser(),
                size=args.size,
                quality=args.quality,
                input_fidelity=args.input_fidelity,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as exc:  # noqa: BLE001 — CLI surface
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    cli_main()
