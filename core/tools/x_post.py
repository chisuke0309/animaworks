# AnimaWorks - Digital Anima Framework
# Copyright (C) 2026 AnimaWorks Authors
# SPDX-License-Identifier: Apache-2.0
#
# This file is part of AnimaWorks core/server, licensed under Apache-2.0.
# See LICENSE for the full license text.

"""X (Twitter) Post tool for AnimaWorks.

Posts tweets and threads via X API v2 with OAuth 1.0a authentication.
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
import time
import urllib.parse
import uuid
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

    def post_tweet(self, text: str) -> dict:
        """Post a single tweet.

        Args:
            text: Tweet text (max 280 characters).

        Returns:
            API response dict with tweet id and text.
        """
        if len(text) > 280:
            raise ValueError(f"Tweet text too long ({len(text)} chars, max 280).")
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
            if len(text) > 280:
                raise ValueError(
                    f"Tweet #{i + 1} too long ({len(text)} chars, max 280)."
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
# Anthropic tool_use schemas
# ---------------------------------------------------------------------------

def get_tool_schemas() -> list[dict]:
    """Return Anthropic tool_use schemas for X post tools."""
    return [
        {
            "name": "x_post",
            "description": (
                "Post a tweet to X (Twitter). "
                "Text must be 280 characters or less. "
                "Use this to share news, insights, or AI/DX trend summaries."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Tweet text (max 280 characters).",
                    },
                },
                "required": ["text"],
            },
        },
        {
            "name": "x_post_thread",
            "description": (
                "Post a thread (multiple connected tweets) to X (Twitter). "
                "Each tweet must be 280 characters or less. "
                "Use this for longer articles or step-by-step explanations."
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
    ]


# ── Dispatch ──────────────────────────────────────────

def dispatch(name: str, args: dict[str, Any]) -> Any:
    """Dispatch a tool call by schema name."""
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
