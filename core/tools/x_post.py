# AnimaWorks - Digital Anima Framework
# Copyright (C) 2026 AnimaWorks Authors
# SPDX-License-Identifier: Apache-2.0
#
# This file is part of AnimaWorks core/server, licensed under Apache-2.0.
# See LICENSE for the full license text.

"""X (Twitter) Post tool for AnimaWorks.

Posts tweets and threads via X API v2 with OAuth 1.0a authentication.
Includes pending approval flow: save_pending → Web UI approve → execute_pending.

Credentials are read from .env:
  TWITTER_API_KEY, TWITTER_API_SECRET,
  TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import time
import urllib.parse
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import re

from difflib import SequenceMatcher

import httpx

from core.tools._base import ToolConfigError, get_credential, logger


def _strip_markdown(text: str) -> str:
    """Remove Markdown formatting that has no effect on X (Twitter).

    Strips bold (``**``/``__``), italic (``*``/``_``), inline code
    (`` ` ``), strikethrough (``~~``), and heading markers (``# ``).
    """
    # Bold / italic: **text**, __text__, *text*, _text_
    text = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}(.+?)_{1,3}", r"\1", text)
    # Strikethrough: ~~text~~
    text = re.sub(r"~~(.+?)~~", r"\1", text)
    # Inline code: `text`
    text = re.sub(r"`(.+?)`", r"\1", text)
    # Heading markers: # / ## / ###
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Bullet markers: - item / * item (preserve the text)
    text = re.sub(r"^[\-\*]\s+", "・", text, flags=re.MULTILINE)
    return text

# ── Execution Profile ─────────────────────────────────────

EXECUTION_PROFILE: dict[str, dict[str, object]] = {
    "post": {"expected_seconds": 10, "background_eligible": False},
    "thread": {"expected_seconds": 30, "background_eligible": False},
}


# ---------------------------------------------------------------------------
# OAuth 1.0a signer
# ---------------------------------------------------------------------------

def _oauth1_header(
    method: str,
    url: str,
    api_key: str,
    api_secret: str,
    access_token: str,
    access_token_secret: str,
) -> str:
    """Build an OAuth 1.0a Authorization header for X API v2.

    X API v2 uses JSON body — body params are NOT included in the signature.
    Only OAuth header params are signed.
    """
    oauth_params = {
        "oauth_consumer_key": api_key,
        "oauth_nonce": uuid.uuid4().hex,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": access_token,
        "oauth_version": "1.0",
    }

    # Percent-encode each key and value, then sort alphabetically
    encoded = {
        urllib.parse.quote(k, safe=""): urllib.parse.quote(v, safe="")
        for k, v in oauth_params.items()
    }
    param_string = "&".join(
        f"{k}={v}" for k, v in sorted(encoded.items())
    )

    # Signature base string
    base_string = "&".join([
        method.upper(),
        urllib.parse.quote(url, safe=""),
        urllib.parse.quote(param_string, safe=""),
    ])

    # Signing key
    signing_key = (
        urllib.parse.quote(api_secret, safe="")
        + "&"
        + urllib.parse.quote(access_token_secret, safe="")
    )

    # HMAC-SHA1
    digest = hmac.new(
        signing_key.encode("utf-8"),
        base_string.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    signature = base64.b64encode(digest).decode("utf-8")

    # Build Authorization header
    oauth_params["oauth_signature"] = signature
    header_parts = ", ".join(
        f'{urllib.parse.quote(k, safe="")}="{urllib.parse.quote(v, safe="")}"'
        for k, v in sorted(oauth_params.items())
    )
    return f"OAuth {header_parts}"


# ---------------------------------------------------------------------------
# X Post client
# ---------------------------------------------------------------------------

class XPostClient:
    """X (Twitter) API v2 client for posting tweets."""

    TWEETS_URL = "https://api.twitter.com/2/tweets"

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        access_token: str | None = None,
        access_token_secret: str | None = None,
    ) -> None:
        self.api_key = api_key or get_credential(
            "x_twitter", "x_post", env_var="TWITTER_API_KEY"
        )
        self.api_secret = api_secret or get_credential(
            "x_twitter", "x_post", key_name="api_secret", env_var="TWITTER_API_SECRET"
        )
        self.access_token = access_token or get_credential(
            "x_twitter", "x_post", key_name="access_token", env_var="TWITTER_ACCESS_TOKEN"
        )
        self.access_token_secret = access_token_secret or get_credential(
            "x_twitter", "x_post", key_name="access_token_secret", env_var="TWITTER_ACCESS_TOKEN_SECRET"
        )

    def _post(self, body: dict[str, Any]) -> dict:
        """Send a POST /tweets request."""
        auth_header = _oauth1_header(
            method="POST",
            url=self.TWEETS_URL,
            api_key=self.api_key,
            api_secret=self.api_secret,
            access_token=self.access_token,
            access_token_secret=self.access_token_secret,
        )

        response = httpx.post(
            self.TWEETS_URL,
            json=body,
            headers={
                "Authorization": auth_header,
                "Content-Type": "application/json",
                "User-Agent": "AnimaWorks/1.0",
            },
            timeout=30.0,
        )

        if response.status_code == 429:
            raise RuntimeError("Rate limit exceeded. Try again later.")
        if response.status_code == 401:
            raise RuntimeError("OAuth authentication failed. Check credentials.")
        if response.status_code == 403:
            raise RuntimeError(f"Access forbidden: {response.text}")

        response.raise_for_status()
        return response.json()

    # X Premium allows up to 25,000 characters per post.
    MAX_CHARS = 25_000
    # Legacy 280-char limit for threads (each individual tweet).
    MAX_CHARS_THREAD = 280

    def post_tweet(self, text: str) -> dict:
        """Post a single tweet.

        Args:
            text: Tweet text (max 25,000 characters for X Premium).

        Returns:
            API response dict with tweet id and text.
        """
        text = _strip_markdown(text)
        if len(text) > self.MAX_CHARS:
            raise ValueError(f"Tweet text too long ({len(text)} chars, max {self.MAX_CHARS}).")
        result = self._post({"text": text})
        tweet_id = result.get("data", {}).get("id", "")
        logger.info("Tweet posted: id=%s", tweet_id)
        return result

    def post_thread(self, texts: list[str]) -> list[dict]:
        """Post a thread (multiple connected tweets).

        Args:
            texts: List of tweet texts. Each must be ≤280 characters.

        Returns:
            List of API response dicts, one per tweet.
        """
        if not texts:
            raise ValueError("texts must not be empty.")

        results: list[dict] = []
        reply_to_id: str | None = None

        for i, text in enumerate(texts):
            if len(text) > self.MAX_CHARS_THREAD:
                raise ValueError(
                    f"Tweet #{i + 1} too long ({len(text)} chars, max {self.MAX_CHARS_THREAD})."
                )
            body: dict[str, Any] = {"text": text}
            if reply_to_id:
                body["reply"] = {"in_reply_to_tweet_id": reply_to_id}

            result = self._post(body)
            tweet_id = result.get("data", {}).get("id", "")
            logger.info("Thread tweet #%d posted: id=%s", i + 1, tweet_id)
            results.append(result)
            reply_to_id = tweet_id

        return results


# ---------------------------------------------------------------------------
# Pending post approval flow
# ---------------------------------------------------------------------------

PENDING_DIR = Path(os.path.expanduser("~/.animaworks/pending_posts"))


def _ensure_pending_dir() -> Path:
    """Ensure the pending posts directory exists."""
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    return PENDING_DIR


def _notify_pending_post(
    draft_id: str,
    text: str,
    slot: str,
    anima: str,
    scoring: dict | None = None,
    *,
    auto_approved: bool = False,
) -> None:
    """Fire-and-forget Telegram notification for a new pending post.

    Works from both async contexts (FastAPI event loop) and sync contexts
    (tool execution in a worker thread via run_in_executor).
    """
    import asyncio
    import threading

    async def _send() -> None:
        try:
            from core.config.models import load_config
            from core.notification.notifier import HumanNotifier

            config = load_config()
            notifier = HumanNotifier.from_config(config.human_notification)
            if not notifier.channel_count:
                return

            preview = text[:300] + ("…" if len(text) > 300 else "")

            # Build score summary
            score_line = ""
            if scoring:
                overall = scoring.get("overall", 0)
                sim = scoring.get("max_similarity", 0)
                score_line = f"品質スコア: {overall}/10.0 (類似度: {sim:.0%})\n"

            if auto_approved:
                subject = f"✅ X投稿 自動承認: {slot} ({anima})"
                action = "自動承認されました。次のcron実行で投稿されます。"
            else:
                subject = f"📝 X投稿 承認依頼: {slot} ({anima})"
                action = "「OK」と返信して承認してください。"

            body = (
                f"ID: {draft_id}\n"
                f"文字数: {len(text)}\n"
                f"{score_line}\n"
                f"{preview}\n\n"
                f"{action}"
            )
            priority = "normal" if not auto_approved else "low"
            await notifier.notify(subject, body, priority=priority, anima_name=anima)
        except Exception:
            logger.warning("Failed to send approval notification for %s", draft_id, exc_info=True)

    # Try scheduling in the running event loop (async context)
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_send(), name=f"notify-pending-{draft_id}")
        return
    except RuntimeError:
        pass

    # Fallback: called from a worker thread (run_in_executor).
    # Run the async notification in a new thread with its own event loop
    # so we don't block the caller.
    def _send_in_thread() -> None:
        try:
            asyncio.run(_send())
        except Exception:
            logger.warning("Failed to send approval notification (thread) for %s", draft_id, exc_info=True)

    t = threading.Thread(target=_send_in_thread, name=f"notify-pending-{draft_id}", daemon=True)
    t.start()


# ── Quality scoring ───────────────────────────────────────────

# Thresholds (0.0–10.0 scale)
_SCORE_AUTO_REJECT = 4.0    # Below this → auto-reject (not saved)
_SCORE_AUTO_APPROVE = 8.5   # Above this → auto-approve (skip human review)
_SIMILARITY_THRESHOLD = 0.85  # Max similarity to any recent post


def _collect_recent_texts(limit: int = 20) -> list[str]:
    """Collect recent post texts from pending_posts dir for similarity check."""
    texts: list[str] = []
    if not PENDING_DIR.exists():
        return texts
    for fp in sorted(PENDING_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True):
        if len(texts) >= limit:
            break
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            if t := data.get("text"):
                texts.append(t)
        except (json.JSONDecodeError, OSError):
            continue
    return texts


def _max_similarity(text: str, recent_texts: list[str]) -> float:
    """Return the highest similarity ratio against recent posts."""
    if not recent_texts:
        return 0.0
    best = 0.0
    for prev in recent_texts:
        ratio = SequenceMatcher(None, text, prev).ratio()
        if ratio > best:
            best = ratio
    return best


def _score_post(text: str) -> dict:
    """Score a post on quality dimensions.

    Returns dict with per-dimension scores, overall score (0.0–10.0),
    max_similarity, and gate decision.
    """
    scores: dict[str, float] = {}
    char_count = len(text)

    # 1. Character count — optimal range 500–2000
    if 500 <= char_count <= 2000:
        scores["char_count"] = 10.0
    elif 200 <= char_count < 500:
        scores["char_count"] = 6.0
    elif 2000 < char_count <= 3000:
        scores["char_count"] = 7.0
    elif char_count < 100:
        scores["char_count"] = 2.0
    elif char_count < 200:
        scores["char_count"] = 4.0
    else:
        scores["char_count"] = 5.0

    # 2. Hashtag count — optimal 3–5
    hashtags = re.findall(r"#\S+", text)
    n_tags = len(hashtags)
    if 3 <= n_tags <= 5:
        scores["hashtags"] = 10.0
    elif 1 <= n_tags <= 2:
        scores["hashtags"] = 6.0
    elif n_tags > 5:
        scores["hashtags"] = 5.0
    else:
        scores["hashtags"] = 2.0

    # 3. Structure — paragraphs, not a wall of text
    lines = [ln for ln in text.strip().split("\n") if ln.strip()]
    if len(lines) >= 4:
        scores["structure"] = 10.0
    elif len(lines) >= 2:
        scores["structure"] = 7.0
    else:
        scores["structure"] = 3.0

    # 4. Hook — first line length and impact
    first_line = lines[0] if lines else ""
    if len(first_line) >= 20:
        scores["hook"] = 8.0
    elif len(first_line) >= 10:
        scores["hook"] = 5.0
    else:
        scores["hook"] = 2.0

    # 5. Originality — similarity to recent posts
    recent = _collect_recent_texts()
    max_sim = _max_similarity(text, recent)
    scores["originality"] = max(0.0, 10.0 * (1.0 - max_sim))

    # Weighted overall
    weights = {
        "char_count": 0.15,
        "hashtags": 0.10,
        "structure": 0.10,
        "hook": 0.15,
        "originality": 0.50,
    }
    overall = round(sum(scores[k] * weights[k] for k in weights), 1)

    # Gate decision
    if max_sim >= _SIMILARITY_THRESHOLD:
        gate = "rejected"
        gate_reason = f"過去投稿と類似度 {max_sim:.0%} (閾値 {_SIMILARITY_THRESHOLD:.0%})"
    elif overall < _SCORE_AUTO_REJECT:
        gate = "rejected"
        gate_reason = f"品質スコア {overall} < {_SCORE_AUTO_REJECT} (自動棄却ライン)"
    elif overall >= _SCORE_AUTO_APPROVE:
        gate = "auto_approved"
        gate_reason = f"品質スコア {overall} ≧ {_SCORE_AUTO_APPROVE} (自動承認ライン)"
    else:
        gate = "pending"
        gate_reason = f"品質スコア {overall} — 人間レビュー待ち"

    return {
        "scores": scores,
        "overall": overall,
        "max_similarity": round(max_sim, 3),
        "gate": gate,
        "gate_reason": gate_reason,
    }


# ── Save pending post ─────────────────────────────────────────


def save_pending_post(text: str, slot: str, anima: str = "unknown") -> dict:
    """Save a tweet draft for human approval.

    Creates a JSON file in ~/.animaworks/pending_posts/.
    Runs quality scoring — auto-rejects low-quality posts and
    auto-approves high-quality posts.

    Args:
        text: Tweet text.
        slot: Time slot label (e.g. 'morning', 'evening').
        anima: Name of the anima saving the draft.

    Returns:
        Dict with draft id, score, and gate decision.
    """
    _ensure_pending_dir()
    text = _strip_markdown(text)

    # ── Dedup: check if identical or near-identical content already exists ──
    try:
        for _existing_file in PENDING_DIR.glob("*.json"):
            _existing = json.loads(_existing_file.read_text(encoding="utf-8"))
            _existing_text = _existing.get("text", "")
            # If text is identical (or first 200 chars match), block duplicate save
            if (
                _existing_text == text
                or (len(text) > 200 and _existing_text[:200] == text[:200])
            ) and _existing.get("slot") == slot:
                logger.info(
                    "Duplicate save_pending blocked: slot=%s existing=%s",
                    slot, _existing_file.name,
                )
                return {
                    "success": False,
                    "id": _existing.get("id", "?"),
                    "rejected": True,
                    "quality_score": _existing.get("quality_score", 0),
                    "gate_reason": "duplicate_content",
                    "scores": _existing.get("quality_scores", {}),
                    "message": (
                        f"同じ内容の投稿が既に保存済みです (id={_existing.get('id','?')})。"
                        f"重複保存を防止しました。"
                    ),
                }
    except Exception:
        logger.debug("Dedup check failed, proceeding with save", exc_info=True)

    # Score before saving
    scoring = _score_post(text)
    gate = scoring["gate"]

    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst)
    ts = now.strftime("%Y%m%dT%H%M%S")
    draft_id = f"{ts}_{slot}"
    filename = f"{draft_id}.json"

    # Auto-reject: don't save the file, return immediately
    if gate == "rejected":
        logger.info(
            "Post rejected (score=%.1f sim=%.3f): %s",
            scoring["overall"], scoring["max_similarity"], draft_id,
        )
        return {
            "success": False,
            "id": draft_id,
            "rejected": True,
            "quality_score": scoring["overall"],
            "gate_reason": scoring["gate_reason"],
            "scores": scoring["scores"],
            "message": f"投稿は品質スコアにより棄却されました: {scoring['gate_reason']}",
        }

    status = "approved" if gate == "auto_approved" else "pending"

    draft = {
        "id": draft_id,
        "text": text,
        "slot": slot,
        "anima": anima,
        "created_at": now.isoformat(),
        "status": status,
        "char_count": len(text),
        "quality_score": scoring["overall"],
        "quality_scores": scoring["scores"],
        "max_similarity": scoring["max_similarity"],
        "gate": gate,
        "gate_reason": scoring["gate_reason"],
    }

    filepath = PENDING_DIR / filename
    filepath.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")

    if gate == "auto_approved":
        logger.info(
            "Post auto-approved (score=%.1f): %s (%d chars)",
            scoring["overall"], draft_id, len(text),
        )
    else:
        logger.info(
            "Pending post saved (score=%.1f): %s (%d chars)",
            scoring["overall"], draft_id, len(text),
        )

    # Send Telegram notification for approval (skip for auto-approved)
    if status == "pending":
        _notify_pending_post(draft_id, text, slot, anima, scoring)
    else:
        _notify_pending_post(draft_id, text, slot, anima, scoring, auto_approved=True)

    status_label = "自動承認" if gate == "auto_approved" else "承認待ち"
    return {
        "success": True,
        "id": draft_id,
        "path": str(filepath),
        "status": status,
        "quality_score": scoring["overall"],
        "gate": gate,
        "gate_reason": scoring["gate_reason"],
        "scores": scoring["scores"],
        "message": f"Draft saved ({status_label}, score={scoring['overall']})",
    }


def execute_pending_posts(slot: str, anima_dir: str = "") -> dict:
    """Execute approved pending posts for a given slot.

    Finds all approved posts matching the slot, posts them via X API,
    and deletes the files on success.  If *anima_dir* is provided the
    tweet_id is written back to ``knowledge/x_post_log.md``.

    Args:
        slot: Time slot to process (e.g. 'morning', 'evening').
        anima_dir: Path to the executing anima's data directory.

    Returns:
        Dict with results.
    """
    _ensure_pending_dir()
    posted = []
    errors = []

    for filepath in sorted(PENDING_DIR.glob("*.json")):
        try:
            draft = json.loads(filepath.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        if draft.get("status") != "approved" or draft.get("slot") != slot:
            continue

        try:
            client = XPostClient()
            result = client.post_tweet(text=draft["text"])
            tweet_id = result.get("data", {}).get("id", "")
            logger.info("Pending post executed: %s → tweet %s", draft["id"], tweet_id)

            # Write tweet_id back to x_post_log.md
            if anima_dir and tweet_id:
                _update_log_tweet_id(Path(anima_dir), tweet_id)

            filepath.unlink()  # Delete on success
            posted.append({
                "id": draft["id"],
                "tweet_id": tweet_id,
                "url": f"https://x.com/i/web/status/{tweet_id}",
            })
        except Exception as e:
            logger.error("Failed to execute pending post %s: %s", draft["id"], e)
            errors.append({"id": draft["id"], "error": str(e)})

    return {
        "success": len(errors) == 0,
        "slot": slot,
        "posted": posted,
        "posted_count": len(posted),
        "errors": errors,
        "message": f"{len(posted)} post(s) executed for slot '{slot}'" if posted else f"No approved posts for slot '{slot}'",
    }


# ---------------------------------------------------------------------------
# Engagement feedback helpers
# ---------------------------------------------------------------------------

def _update_log_tweet_id(anima_dir: Path, tweet_id: str) -> None:
    """Replace the first ``pending`` cell in x_post_log.md with *tweet_id*."""
    log_path = anima_dir / "knowledge" / "x_post_log.md"
    if not log_path.exists():
        return
    try:
        text = log_path.read_text(encoding="utf-8")
        # Replace exactly one occurrence of "| pending |" with the real tweet_id
        updated = text.replace("| pending |", f"| {tweet_id} |", 1)
        if updated != text:
            log_path.write_text(updated, encoding="utf-8")
            logger.info("x_post_log.md: pending → %s", tweet_id)
    except OSError:
        logger.warning("Failed to update x_post_log.md with tweet_id", exc_info=True)


def update_engagement(anima_dir: str) -> dict[str, Any]:
    """Fetch engagement metrics for recent tweets and update x_post_log.md.

    Reads the markdown table, finds rows where tweet_id is numeric and
    any metric column is ``-``, queries the X API, and writes back.

    Args:
        anima_dir: Path to the anima data directory (auto-injected).

    Returns:
        Dict with success status and update count.
    """
    if not anima_dir:
        return {"success": False, "error": "anima_dir not set"}

    log_path = Path(anima_dir) / "knowledge" / "x_post_log.md"
    if not log_path.exists():
        return {"success": False, "error": "x_post_log.md not found"}

    try:
        lines = log_path.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        return {"success": False, "error": str(e)}

    # Find rows with numeric tweet_id and at least one "-" metric
    ids_to_fetch: list[str] = []
    row_indices: dict[str, int] = {}  # tweet_id → line index

    for i, line in enumerate(lines):
        if not line.startswith("|"):
            continue
        cols = [c.strip() for c in line.split("|")]
        # Expected: ['', '日付', 'トピック要約', 'tweet_id', 'likes', 'RTs', 'impressions', '']
        if len(cols) < 8:
            continue
        tid = cols[3]
        if not tid.isdigit():
            continue
        # Check if any metric is still "-"
        if "-" in (cols[4], cols[5], cols[6]):
            ids_to_fetch.append(tid)
            row_indices[tid] = i

    if not ids_to_fetch:
        return {"success": True, "updated": 0, "message": "All metrics up to date"}

    # Fetch metrics from X API
    try:
        from core.tools.x_search import XSearchClient
        client = XSearchClient()
        metrics = client.get_tweet_metrics(ids_to_fetch)
    except Exception as e:
        logger.warning("Failed to fetch tweet metrics: %s", e)
        return {"success": False, "error": f"API error: {e}", "tweet_ids": ids_to_fetch}

    # Update rows
    updated_count = 0
    for tid, m in metrics.items():
        idx = row_indices.get(tid)
        if idx is None:
            continue
        cols = [c.strip() for c in lines[idx].split("|")]
        cols[4] = str(m.get("likes", 0))
        cols[5] = str(m.get("retweets", 0))
        cols[6] = str(m.get("impressions", 0))
        lines[idx] = "| " + " | ".join(cols[1:-1]) + " |"
        updated_count += 1

    if updated_count:
        log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        logger.info("x_post_log.md: updated engagement for %d tweets", updated_count)

    return {
        "success": True,
        "updated": updated_count,
        "tweet_ids": list(metrics.keys()),
        "message": f"Engagement updated for {updated_count} tweet(s)",
    }


# ---------------------------------------------------------------------------
# Anthropic tool_use schemas
# ---------------------------------------------------------------------------

def get_tool_schemas() -> list[dict]:
    """Return Anthropic tool_use schemas for X post tools."""
    return [
        {
            "name": "x_post",
            "description": (
                "Post a tweet to X (Twitter). "
                "X Premium account: up to 25,000 characters per post. "
                "Use this to share news, insights, or AI/DX trend summaries."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Tweet text (X Premium: max 25,000 characters).",
                    },
                },
                "required": ["text"],
            },
        },
        {
            "name": "x_post_thread",
            "description": (
                "Post a thread (multiple connected tweets) to X (Twitter). "
                "Each tweet must be 280 characters or less (thread limit). "
                "Note: For long-form content, prefer single post (up to 25,000 chars) over threads."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "texts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "List of tweet texts in order. "
                            "Each must be ≤280 characters. "
                            "Typically 3-7 tweets for a good thread."
                        ),
                    },
                },
                "required": ["texts"],
            },
        },
        {
            "name": "x_post_save_pending",
            "description": (
                "Save a tweet draft for human approval before posting to X. "
                "The draft will appear in the Web UI for review. "
                "Do NOT post directly with x_post — always use this tool instead."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Tweet text (X Premium: max 25,000 characters).",
                    },
                    "slot": {
                        "type": "string",
                        "description": "Time slot label (e.g. 'morning', 'evening').",
                    },
                },
                "required": ["text", "slot"],
            },
        },
        {
            "name": "x_post_execute_pending",
            "description": (
                "Execute approved pending posts for a given time slot. "
                "Used by cron to post drafts that have been approved in the Web UI. "
                "Do NOT call this from LLM sessions — it is cron-only."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "slot": {
                        "type": "string",
                        "description": "Time slot to process (e.g. 'morning', 'evening').",
                    },
                },
                "required": ["slot"],
            },
        },
        {
            "name": "x_post_update_engagement",
            "description": (
                "Fetch engagement metrics (likes, RTs, impressions) for recent tweets "
                "and update knowledge/x_post_log.md. Cron-only."
            ),
            "input_schema": {
                "type": "object",
                "properties": {},
            },
        },
    ]


# ── Dispatch ──────────────────────────────────────────

def dispatch(name: str, args: dict[str, Any]) -> Any:
    """Dispatch a tool call by schema name."""

    if name == "x_post_save_pending":
        anima_dir = args.pop("anima_dir", "")
        anima_name = Path(anima_dir).name if anima_dir else "unknown"
        return save_pending_post(
            text=args["text"],
            slot=args["slot"],
            anima=anima_name,
        )

    if name == "x_post_execute_pending":
        anima_dir = args.get("anima_dir", "")
        return execute_pending_posts(slot=args["slot"], anima_dir=anima_dir)

    if name == "x_post_update_engagement":
        anima_dir = args.get("anima_dir", "")
        return update_engagement(anima_dir=anima_dir)

    client = XPostClient()

    if name == "x_post":
        result = client.post_tweet(text=args["text"])
        tweet_id = result.get("data", {}).get("id", "")
        return {
            "success": True,
            "tweet_id": tweet_id,
            "url": f"https://x.com/i/web/status/{tweet_id}",
            "text": args["text"],
        }

    if name == "x_post_thread":
        results = client.post_thread(texts=args["texts"])
        first_id = results[0].get("data", {}).get("id", "") if results else ""
        return {
            "success": True,
            "tweet_count": len(results),
            "first_tweet_id": first_id,
            "url": f"https://x.com/i/web/status/{first_id}",
            "texts": args["texts"],
        }

    raise ValueError(f"Unknown tool: {name}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def cli_main(argv: list[str] | None = None) -> None:
    """CLI entry point for x_post."""
    parser = argparse.ArgumentParser(
        description="Post to X (Twitter) via API v2",
    )
    subparsers = parser.add_subparsers(dest="command")

    # post subcommand
    post_parser = subparsers.add_parser("post", help="Post a single tweet")
    post_parser.add_argument("text", help="Tweet text (max 280 chars)")
    post_parser.add_argument("-j", "--json", action="store_true", help="Output as JSON")

    # thread subcommand
    thread_parser = subparsers.add_parser("thread", help="Post a thread")
    thread_parser.add_argument(
        "texts",
        nargs="+",
        help="Tweet texts in order (quote each tweet)",
    )
    thread_parser.add_argument("-j", "--json", action="store_true", help="Output as JSON")

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return

    client = XPostClient()

    if args.command == "post":
        result = client.post_tweet(args.text)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            tweet_id = result.get("data", {}).get("id", "")
            print(f"✓ Posted: https://x.com/i/web/status/{tweet_id}")

    elif args.command == "thread":
        results = client.post_thread(args.texts)
        if args.json:
            print(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            first_id = results[0].get("data", {}).get("id", "") if results else ""
            print(f"✓ Thread ({len(results)} tweets): https://x.com/i/web/status/{first_id}")
