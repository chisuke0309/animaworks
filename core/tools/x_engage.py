# AnimaWorks - Digital Anima Framework
# Copyright (C) 2026 AnimaWorks Authors
# SPDX-License-Identifier: Apache-2.0
#
# This file is part of AnimaWorks core/server, licensed under Apache-2.0.
# See LICENSE for the full license text.

"""X (Twitter) Engagement tools for AnimaWorks.

Provides like, reply, and quote tweet actions via X API v2
with OAuth 1.0a authentication.

Credentials are read from .env:
  TWITTER_API_KEY, TWITTER_API_SECRET,
  TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET
"""
from __future__ import annotations

import json
from typing import Any

import httpx

from core.tools._base import get_credential, logger
from core.tools.x_post import _oauth1_header


# ── Execution Profile ─────────────────────────────────────

EXECUTION_PROFILE: dict[str, dict[str, object]] = {
    "like": {"expected_seconds": 5, "background_eligible": False},
    "reply": {"expected_seconds": 10, "background_eligible": False},
    "quote": {"expected_seconds": 10, "background_eligible": False},
}


# ---------------------------------------------------------------------------
# X Engage client
# ---------------------------------------------------------------------------

class XEngageClient:
    """X (Twitter) API v2 client for engagement actions."""

    TWEETS_URL = "https://api.twitter.com/2/tweets"
    USERS_URL = "https://api.twitter.com/2/users"

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        access_token: str | None = None,
        access_token_secret: str | None = None,
    ) -> None:
        self.api_key = api_key or get_credential(
            "x_twitter", "x_engage", env_var="TWITTER_API_KEY"
        )
        self.api_secret = api_secret or get_credential(
            "x_twitter", "x_engage", key_name="api_secret", env_var="TWITTER_API_SECRET"
        )
        self.access_token = access_token or get_credential(
            "x_twitter", "x_engage", key_name="access_token", env_var="TWITTER_ACCESS_TOKEN"
        )
        self.access_token_secret = access_token_secret or get_credential(
            "x_twitter", "x_engage", key_name="access_token_secret", env_var="TWITTER_ACCESS_TOKEN_SECRET"
        )

    def _get_user_id(self) -> str:
        """Get the authenticated user's ID from /2/users/me."""
        url = f"{self.USERS_URL}/me"
        auth_header = _oauth1_header(
            method="GET",
            url=url,
            api_key=self.api_key,
            api_secret=self.api_secret,
            access_token=self.access_token,
            access_token_secret=self.access_token_secret,
        )
        resp = httpx.get(
            url,
            headers={
                "Authorization": auth_header,
                "User-Agent": "AnimaWorks/1.0",
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        return resp.json()["data"]["id"]

    def _post_json(self, url: str, body: dict[str, Any]) -> dict:
        """Send a POST request with JSON body using OAuth 1.0a."""
        auth_header = _oauth1_header(
            method="POST",
            url=url,
            api_key=self.api_key,
            api_secret=self.api_secret,
            access_token=self.access_token,
            access_token_secret=self.access_token_secret,
        )
        resp = httpx.post(
            url,
            json=body,
            headers={
                "Authorization": auth_header,
                "Content-Type": "application/json",
                "User-Agent": "AnimaWorks/1.0",
            },
            timeout=30.0,
        )
        if resp.status_code == 429:
            raise RuntimeError("Rate limit exceeded. Try again later.")
        if resp.status_code == 401:
            raise RuntimeError("OAuth authentication failed. Check credentials.")
        if resp.status_code == 403:
            raise RuntimeError(f"Access forbidden: {resp.text}")
        resp.raise_for_status()
        return resp.json()

    # ── Like ──────────────────────────────────────────

    def like_tweet(self, tweet_id: str) -> dict:
        """Like a tweet.

        POST /2/users/:id/likes
        Body: {"tweet_id": "..."}
        """
        user_id = self._get_user_id()
        url = f"{self.USERS_URL}/{user_id}/likes"
        result = self._post_json(url, {"tweet_id": tweet_id})
        liked = result.get("data", {}).get("liked", False)
        logger.info("Like tweet %s: liked=%s", tweet_id, liked)
        return {"success": True, "tweet_id": tweet_id, "liked": liked}

    # ── Reply ─────────────────────────────────────────

    def reply_to_tweet(self, tweet_id: str, text: str) -> dict:
        """Reply to a tweet.

        POST /2/tweets
        Body: {"text": "...", "reply": {"in_reply_to_tweet_id": "..."}}
        """
        if not text.strip():
            raise ValueError("Reply text must not be empty.")
        body: dict[str, Any] = {
            "text": text,
            "reply": {"in_reply_to_tweet_id": tweet_id},
        }
        result = self._post_json(self.TWEETS_URL, body)
        reply_id = result.get("data", {}).get("id", "")
        logger.info("Reply to %s: reply_id=%s", tweet_id, reply_id)
        return {
            "success": True,
            "tweet_id": tweet_id,
            "reply_id": reply_id,
            "url": f"https://x.com/i/web/status/{reply_id}",
            "text": text,
        }

    # ── Quote ─────────────────────────────────────────

    def quote_tweet(self, tweet_id: str, text: str) -> dict:
        """Quote tweet (repost with comment).

        POST /2/tweets
        Body: {"text": "...", "quote_tweet_id": "..."}
        """
        if not text.strip():
            raise ValueError("Quote text must not be empty.")
        body: dict[str, Any] = {
            "text": text,
            "quote_tweet_id": tweet_id,
        }
        result = self._post_json(self.TWEETS_URL, body)
        quote_id = result.get("data", {}).get("id", "")
        logger.info("Quote tweet %s: quote_id=%s", tweet_id, quote_id)
        return {
            "success": True,
            "tweet_id": tweet_id,
            "quote_id": quote_id,
            "url": f"https://x.com/i/web/status/{quote_id}",
            "text": text,
        }


# ---------------------------------------------------------------------------
# Anthropic tool_use schemas
# ---------------------------------------------------------------------------

def get_tool_schemas() -> list[dict]:
    """Return Anthropic tool_use schemas for X engagement tools."""
    return [
        {
            "name": "x_like",
            "description": (
                "Like a tweet on X (Twitter). "
                "Use this to engage with relevant content from target accounts. "
                "Provide the tweet ID to like."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "tweet_id": {
                        "type": "string",
                        "description": "The ID of the tweet to like.",
                    },
                },
                "required": ["tweet_id"],
            },
        },
        {
            "name": "x_reply",
            "description": (
                "Reply to a tweet on X (Twitter). "
                "Use this to engage with target accounts by providing valuable, "
                "relevant replies. Keep replies concise and insightful."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "tweet_id": {
                        "type": "string",
                        "description": "The ID of the tweet to reply to.",
                    },
                    "text": {
                        "type": "string",
                        "description": "Reply text (max 280 characters recommended for visibility).",
                    },
                },
                "required": ["tweet_id", "text"],
            },
        },
        {
            "name": "x_quote",
            "description": (
                "Quote tweet (repost with comment) on X (Twitter). "
                "Use this to amplify and add commentary to buzz tweets "
                "from target accounts. Add unique value in your quote."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "tweet_id": {
                        "type": "string",
                        "description": "The ID of the tweet to quote.",
                    },
                    "text": {
                        "type": "string",
                        "description": "Quote comment text.",
                    },
                },
                "required": ["tweet_id", "text"],
            },
        },
    ]


# ── Dispatch ──────────────────────────────────────────

def dispatch(name: str, args: dict[str, Any]) -> Any:
    """Dispatch a tool call by schema name."""
    client = XEngageClient()

    if name == "x_like":
        return client.like_tweet(tweet_id=args["tweet_id"])

    if name == "x_reply":
        return client.reply_to_tweet(
            tweet_id=args["tweet_id"],
            text=args["text"],
        )

    if name == "x_quote":
        return client.quote_tweet(
            tweet_id=args["tweet_id"],
            text=args["text"],
        )

    raise ValueError(f"Unknown tool: {name}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def cli_main(argv: list[str] | None = None) -> None:
    """CLI entry point for x_engage."""
    import argparse

    parser = argparse.ArgumentParser(
        description="X (Twitter) engagement actions via API v2",
    )
    subparsers = parser.add_subparsers(dest="command")

    like_p = subparsers.add_parser("like", help="Like a tweet")
    like_p.add_argument("tweet_id", help="Tweet ID to like")

    reply_p = subparsers.add_parser("reply", help="Reply to a tweet")
    reply_p.add_argument("tweet_id", help="Tweet ID to reply to")
    reply_p.add_argument("text", help="Reply text")

    quote_p = subparsers.add_parser("quote", help="Quote tweet")
    quote_p.add_argument("tweet_id", help="Tweet ID to quote")
    quote_p.add_argument("text", help="Quote comment text")

    parsed = parser.parse_args(argv)

    if not parsed.command:
        parser.print_help()
        return

    client = XEngageClient()

    if parsed.command == "like":
        result = client.like_tweet(parsed.tweet_id)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif parsed.command == "reply":
        result = client.reply_to_tweet(parsed.tweet_id, parsed.text)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif parsed.command == "quote":
        result = client.quote_tweet(parsed.tweet_id, parsed.text)
        print(json.dumps(result, indent=2, ensure_ascii=False))
