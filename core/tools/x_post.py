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

import httpx

from core.tools._base import ToolConfigError, get_credential, logger

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


def save_pending_post(text: str, slot: str, anima: str = "unknown") -> dict:
    """Save a tweet draft for human approval.

    Creates a JSON file in ~/.animaworks/pending_posts/.

    Args:
        text: Tweet text.
        slot: Time slot label (e.g. 'morning', 'evening').
        anima: Name of the anima saving the draft.

    Returns:
        Dict with draft id and file path.
    """
    _ensure_pending_dir()
    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst)
    ts = now.strftime("%Y%m%dT%H%M%S")
    draft_id = f"{ts}_{slot}"
    filename = f"{draft_id}.json"

    draft = {
        "id": draft_id,
        "text": text,
        "slot": slot,
        "anima": anima,
        "created_at": now.isoformat(),
        "status": "pending",
        "char_count": len(text),
    }

    filepath = PENDING_DIR / filename
    filepath.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Pending post saved: %s (%d chars)", draft_id, len(text))
    return {"success": True, "id": draft_id, "path": str(filepath), "message": "Draft saved for approval"}


def execute_pending_posts(slot: str) -> dict:
    """Execute approved pending posts for a given slot.

    Finds all approved posts matching the slot, posts them via X API,
    and deletes the files on success.

    Args:
        slot: Time slot to process (e.g. 'morning', 'evening').

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
        return execute_pending_posts(slot=args["slot"])

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
