# AnimaWorks - Digital Anima Framework
# Copyright (C) 2026 AnimaWorks Authors
# SPDX-License-Identifier: Apache-2.0

"""Approval flow API for pending X posts."""

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from core.tools.x_post import PENDING_DIR, XPostClient

logger = logging.getLogger("animaworks.server.api.approvals")

router = APIRouter(prefix="/approvals", tags=["approvals"])


def _read_pending_posts() -> list[dict[str, Any]]:
    """Read all pending post JSON files, sorted by created_at descending."""
    if not PENDING_DIR.exists():
        return []
    posts = []
    for fp in sorted(PENDING_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            posts.append(data)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read pending post %s: %s", fp, e)
    return posts


def _get_post_path(post_id: str):
    """Get the file path for a pending post by ID."""
    fp = PENDING_DIR / f"{post_id}.json"
    if not fp.exists():
        raise HTTPException(status_code=404, detail=f"Pending post '{post_id}' not found")
    return fp


@router.get("/posts")
def list_pending_posts() -> list[dict[str, Any]]:
    """List all pending and approved posts."""
    return _read_pending_posts()


@router.get("/posts/{post_id}")
def get_pending_post(post_id: str) -> dict[str, Any]:
    """Get a single pending post by ID."""
    fp = _get_post_path(post_id)
    return json.loads(fp.read_text(encoding="utf-8"))


@router.post("/posts/{post_id}/approve")
def approve_post(post_id: str) -> dict[str, Any]:
    """Approve a pending post (set status to 'approved').

    The approved post will be picked up by the next cron run
    of x_post_execute_pending for its slot.
    """
    fp = _get_post_path(post_id)
    data = json.loads(fp.read_text(encoding="utf-8"))

    if data.get("status") == "approved":
        return {"success": True, "id": post_id, "message": "Already approved"}

    data["status"] = "approved"
    fp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Pending post approved: %s", post_id)
    return {"success": True, "id": post_id, "message": "Post approved — will be posted at next cron run"}


@router.delete("/posts/{post_id}")
def delete_post(post_id: str) -> dict[str, Any]:
    """Delete (discard) a pending post."""
    fp = _get_post_path(post_id)
    fp.unlink()
    logger.info("Pending post deleted: %s", post_id)
    return {"success": True, "id": post_id, "message": "Post discarded"}
