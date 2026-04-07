# AnimaWorks - Digital Anima Framework
# Copyright (C) 2026 AnimaWorks Authors
# SPDX-License-Identifier: Apache-2.0

"""TikTok Studio scraper -- Playwright browser automation.

Private helper for tiktok_analytics.scrape_engagement().
Underscore prefix prevents auto-discovery by discover_core_tools().

Uses Cookie JSON exported via Chrome extension (Cookie-Editor etc.).
Stored at ~/.animaworks/credentials/tiktok_cookies.json.
Cookie refresh: re-export from Chrome extension when session expires (~6 months).
"""
from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("animaworks.tools.tiktok_scraper")

DEFAULT_COOKIE_PATH = Path.home() / ".animaworks" / "credentials" / "tiktok_cookies.json"


# ── Exceptions ───────────────────────────────────────────


class CookieNotFoundError(Exception):
    """Cookie file not found."""


class CookieExpiredError(Exception):
    """TikTok session cookies are expired."""


class PageStructureError(Exception):
    """TikTok Studio DOM structure has changed."""


# ── Cookie Management ────────────────────────────────────

CRITICAL_COOKIES = {"sessionid", "sessionid_ss", "sid_guard"}


def load_cookies(cookie_path: Path) -> list[dict]:
    """Load cookies from a JSON file."""
    if not cookie_path.exists():
        raise CookieNotFoundError(f"Cookie file not found: {cookie_path}")
    data = json.loads(cookie_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise CookieNotFoundError("Cookie file must be a JSON array")
    return data


def validate_cookies(cookies: list[dict]) -> bool:
    """Check that critical TikTok cookies exist and are not expired."""
    names = {c.get("name") for c in cookies}
    if not CRITICAL_COOKIES.issubset(names):
        missing = CRITICAL_COOKIES - names
        logger.warning("Missing critical cookies: %s", missing)
        return False
    now = time.time()
    for c in cookies:
        if c.get("name") in CRITICAL_COOKIES:
            expires = c.get("expires") or c.get("expirationDate") or -1
            if isinstance(expires, (int, float)) and 0 < expires < now:
                logger.warning("Cookie '%s' expired at %s", c["name"], expires)
                return False
    return True


# ── Number Parsing ───────────────────────────────────────


def _parse_number(text: str) -> int:
    """Parse TikTok-formatted numbers: '1.2K' -> 1200, '3.5M' -> 3500000."""
    text = text.strip().replace(",", "").replace("\u00a0", "")
    if not text or text in ("-", "--"):
        return 0
    multipliers = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}
    for suffix, mult in multipliers.items():
        if text.upper().endswith(suffix):
            try:
                return int(float(text[:-1]) * mult)
            except ValueError:
                return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


# ── Browser Automation ───────────────────────────────────


def _format_cookies_for_playwright(cookies: list[dict]) -> list[dict]:
    """Convert exported cookies to Playwright's expected format."""
    formatted = []
    for c in cookies:
        entry: dict[str, Any] = {
            "name": c["name"],
            "value": c["value"],
            "domain": c.get("domain", ".tiktok.com"),
            "path": c.get("path", "/"),
        }
        # Support both "expires" and "expirationDate" (Cookie-Editor format)
        exp = c.get("expires") or c.get("expirationDate")
        if exp and isinstance(exp, (int, float)) and exp > 0:
            entry["expires"] = exp
        if c.get("httpOnly"):
            entry["httpOnly"] = True
        if c.get("secure"):
            entry["secure"] = True
        # Playwright sameSite: "Strict" | "Lax" | "None"
        ss = c.get("sameSite")
        if ss == "no_restriction":
            entry["sameSite"] = "None"
        elif ss == "lax":
            entry["sameSite"] = "Lax"
        elif ss == "strict":
            entry["sameSite"] = "Strict"
        formatted.append(entry)
    return formatted


def scrape_tiktok_studio(
    cookies: list[dict],
    max_posts: int = 20,
    timeout_ms: int = 30_000,
) -> list[dict]:
    """Scrape engagement data from TikTok Studio content page.

    Uses Cookie JSON for authentication (no Google OAuth needed).
    Returns a list of dicts compatible with tiktok_analytics.record_engagement().
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="ja-JP",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        context.add_cookies(_format_cookies_for_playwright(cookies))
        page = context.new_page()

        try:
            page.goto(
                "https://www.tiktok.com/tiktokstudio/content",
                wait_until="domcontentloaded",
                timeout=timeout_ms,
            )
            # Wait for video links to appear (content fully rendered)
            try:
                page.wait_for_selector(
                    'a[href*="/video/"]', timeout=15_000,
                )
            except Exception:
                pass  # Proceed anyway — extraction will handle empty case
            page.wait_for_timeout(2000)

            # Check for login redirect (session expired)
            if "login" in page.url.lower():
                raise CookieExpiredError(
                    "セッション切れ: ログインページにリダイレクトされました。"
                    "Chrome拡張でCookieを再エクスポートしてください。"
                )

            posts = _extract_posts(page, max_posts)
            if not posts:
                debug_dir = Path.home() / ".animaworks" / "tmp"
                debug_dir.mkdir(parents=True, exist_ok=True)
                debug_path = debug_dir / "tiktok_studio_debug.png"
                page.screenshot(path=str(debug_path), full_page=True)
                raise PageStructureError(
                    f"投稿が見つかりません。URL: {page.url}, "
                    f"デバッグスクリーンショット: {debug_path}"
                )
            return posts
        finally:
            browser.close()


# ── Post Extraction ──────────────────────────────────────


def _extract_posts(page: Any, max_posts: int) -> list[dict]:
    """Extract post data from TikTok Studio content page.

    TikTok Studio (2026-04) uses a div-based card layout (NOT <table>).
    Each post card contains a video link ``a[href*="/video/"]``.
    The card level is detected dynamically by walking up from a video link
    until the parent has many sibling cards — this avoids relying on
    CSS-in-JS class names which change across builds.

    Within each card, ``<span>`` elements hold the text values:
    date, privacy setting, and numeric metrics (views, likes, comments)
    in that order.
    """
    posts: list[dict] = []

    video_links = page.query_selector_all('a[href*="/video/"]')
    if not video_links:
        return posts

    card_depth = _detect_card_depth(video_links[0])

    for link in video_links[:max_posts]:
        post = _parse_card(link, card_depth)
        if post and post.get("title"):
            posts.append(post)

    return posts


def _detect_card_depth(link_el: Any) -> int:
    """Walk up from a video link to find the card container depth."""
    el = link_el
    for depth in range(1, 12):
        el = el.evaluate_handle("e => e.parentElement").as_element()
        if not el:
            break
        parent = el.evaluate_handle("e => e.parentElement").as_element()
        if not parent:
            break
        sibling_count = parent.evaluate(
            'p => [...p.children].filter(c => c.querySelector(\'a[href*="/video/"]\')).length'
        )
        if sibling_count and sibling_count > 5:
            return depth
    return 6


def _parse_card(link_el: Any, card_depth: int) -> dict | None:
    """Extract engagement data from a single post card."""
    try:
        href = link_el.get_attribute("href") or ""
        title = link_el.inner_text().strip()[:200]

        card = link_el
        for _ in range(card_depth):
            card = card.evaluate_handle("e => e.parentElement").as_element()
            if not card:
                return None

        span_texts: list[str] = card.evaluate(
            """c => [...c.querySelectorAll('span')]
                .map(s => s.textContent.trim())
                .filter(t => t.length > 0 && t.length < 20)"""
        ) or []

        date_text = ""
        for t in span_texts:
            if "\u6708" in t:  # 月
                date_text = t
                break

        nums: list[int] = []
        for t in span_texts:
            cleaned = t.replace(",", "").replace("\u00a0", "")
            if re.match(r"^[\d]+$", cleaned):
                nums.append(int(cleaned))
            elif re.match(r"^[\d.]+[KMB]$", cleaned, re.IGNORECASE):
                nums.append(_parse_number(cleaned))

        tiktok_url = f"https://www.tiktok.com{href}" if href else ""

        return {
            "title": title,
            "tiktok_url": tiktok_url,
            "posted_at": date_text,
            "views": nums[0] if len(nums) > 0 else 0,
            "likes": nums[1] if len(nums) > 1 else 0,
            "comments": nums[2] if len(nums) > 2 else 0,
            "shares": 0,
            "saves": 0,
        }
    except Exception as exc:
        logger.debug("Failed to parse card: %s", exc)
        return None
