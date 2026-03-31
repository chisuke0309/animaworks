# AnimaWorks - Digital Anima Framework
# Copyright (C) 2026 AnimaWorks Authors
# SPDX-License-Identifier: Apache-2.0

"""TikTok trend research tool for AnimaWorks.

Fetches AI/DX trending keywords from Google Trends and news RSS.
Used by chiro (TikTok調査担当).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import httpx

from core.tools._base import logger

# ── Execution Profile ─────────────────────────────────────

EXECUTION_PROFILE: dict[str, dict[str, object]] = {
    "tiktok_fetch_trends": {"expected_seconds": 30, "background_eligible": True},
    "tiktok_fetch_news": {"expected_seconds": 15, "background_eligible": True},
}

# ── Constants ─────────────────────────────────────────────

AI_KEYWORDS = ["ChatGPT", "Gemini", "Claude", "生成AI", "Copilot", "Perplexity"]
GOOGLE_TRENDS_RSS = "https://trends.google.co.jp/trending/rss?geo=JP"
AI_FILTER_WORDS = ["AI", "GPT", "Claude", "Gemini", "生成", "LLM", "機械学習",
                    "ディープラーニング", "Copilot", "OpenAI", "Anthropic", "Google"]

NEWS_RSS_FEEDS = [
    "https://news.google.com/rss/search?q=生成AI+OR+ChatGPT+OR+Claude+OR+Gemini&hl=ja&gl=JP&ceid=JP:ja",
]

# ── Tool Schemas ──────────────────────────────────────────


def get_tool_schemas() -> list[dict]:
    return [
        {
            "name": "tiktok_fetch_trends",
            "description": (
                "Google TrendsからAI関連キーワードのトレンドデータを取得する。"
                "検索指数・勢い・急上昇ワードを返す。"
                "結果はanima_dir/knowledge/trend_data.jsonにも保存される。"
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "調査するキーワード一覧。省略時はデフォルトのAIキーワード群を使用",
                    },
                },
                "required": [],
            },
        },
        {
            "name": "tiktok_fetch_news",
            "description": (
                "Google News RSSからAI関連の最新ニュースを取得する。"
                "カルーセル企画のネタ元として使う。"
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "max_items": {
                        "type": "integer",
                        "description": "取得するニュース件数（デフォルト10）",
                    },
                },
                "required": [],
            },
        },
    ]


# ── Implementation ────────────────────────────────────────


def _fetch_google_trends_rss() -> list[dict]:
    """Google Trends RSのS急上昇ワードからAI関連を抽出."""
    try:
        resp = httpx.get(GOOGLE_TRENDS_RSS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        logger.warning("Google Trends RSS fetch failed: %s", e)
        return []

    results = []
    try:
        root = ElementTree.fromstring(resp.text)
        for item in root.findall(".//item"):
            title_el = item.find("title")
            traffic_el = item.find("{https://trends.google.co.jp/trending/rss}approx_traffic")
            if title_el is None:
                continue
            title = title_el.text or ""
            # AI関連フィルタ
            if any(w.lower() in title.lower() for w in AI_FILTER_WORDS):
                traffic = traffic_el.text if traffic_el is not None else "N/A"
                results.append({"keyword": title, "traffic": traffic})
    except ElementTree.ParseError:
        logger.warning("Google Trends RSS parse failed")

    return results


def _fetch_keyword_scores(keywords: list[str]) -> dict:
    """pytrends APIでキーワードの検索指数を取得（簡易版）.

    pytrends がインストールされていない場合は空の結果を返す。
    """
    try:
        from pytrends.request import TrendReq
    except ImportError:
        logger.info("pytrends not installed, skipping keyword scores")
        return {"all_scores": {}, "momentum": {}}

    try:
        pytrends = TrendReq(hl="ja-JP", tz=-540)
        pytrends.build_payload(keywords[:5], timeframe="now 7-d", geo="JP")
        df = pytrends.interest_over_time()

        if df.empty:
            return {"all_scores": {}, "momentum": {}}

        all_scores = {}
        momentum = {}
        for kw in keywords[:5]:
            if kw not in df.columns:
                continue
            series = df[kw]
            all_scores[kw] = round(float(series.mean()), 1)
            # 勢い: 後半平均 vs 前半平均
            mid = len(series) // 2
            first_half = series[:mid].mean()
            second_half = series[mid:].mean()
            if first_half > 0:
                momentum[kw] = round(((second_half - first_half) / first_half) * 100, 1)
            else:
                momentum[kw] = 0.0

        # Related queries
        rising = []
        top_queries = []
        try:
            top_kw = max(all_scores, key=all_scores.get) if all_scores else None
            if top_kw:
                related = pytrends.related_queries()
                if top_kw in related:
                    rising_df = related[top_kw].get("rising")
                    top_df = related[top_kw].get("top")
                    if rising_df is not None and not rising_df.empty:
                        rising = rising_df["query"].head(5).tolist()
                    if top_df is not None and not top_df.empty:
                        top_queries = top_df["query"].head(5).tolist()
        except Exception:
            pass

        return {
            "all_scores": all_scores,
            "momentum": momentum,
            "rising_related_queries": rising,
            "top_related_queries": top_queries,
        }
    except Exception as e:
        logger.warning("pytrends fetch failed: %s", e)
        return {"all_scores": {}, "momentum": {}}


def fetch_trends(keywords: list[str] | None = None, anima_dir: str | None = None) -> dict:
    """トレンドデータを取得して返す."""
    kws = keywords or AI_KEYWORDS
    now = datetime.now(timezone.utc).isoformat()

    # Google Trends RSS
    rss_trends = _fetch_google_trends_rss()

    # Keyword scores
    scores_data = _fetch_keyword_scores(kws)

    all_scores = scores_data.get("all_scores", {})
    top_kw = max(all_scores, key=all_scores.get) if all_scores else None

    result = {
        "fetched_at": now,
        "top_keyword": top_kw,
        "top_keyword_score": all_scores.get(top_kw, 0) if top_kw else 0,
        "all_scores": all_scores,
        "momentum": scores_data.get("momentum", {}),
        "ai_trending_rss": rss_trends[:5],
        "rising_related_queries": scores_data.get("rising_related_queries", []),
        "top_related_queries": scores_data.get("top_related_queries", []),
        "theme_hints": [],
    }

    # Generate hints
    if top_kw:
        score = all_scores.get(top_kw, 0)
        mom = scores_data.get("momentum", {}).get(top_kw, 0)
        result["theme_hints"].append(
            f"最注目AIキーワード: {top_kw}（検索指数: {score:.0f}/100、勢い: {mom:+.0f}%）"
        )

    # Save to anima knowledge dir
    if anima_dir:
        out_path = Path(anima_dir) / "knowledge" / "trend_data.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Trend data saved to %s", out_path)

    return {"success": True, "data": result}


def fetch_news(max_items: int = 10, anima_dir: str | None = None) -> dict:
    """AI関連ニュースをRSSから取得."""
    articles = []

    for feed_url in NEWS_RSS_FEEDS:
        try:
            resp = httpx.get(feed_url, timeout=15)
            resp.raise_for_status()
            root = ElementTree.fromstring(resp.text)

            for item in root.findall(".//item"):
                title_el = item.find("title")
                link_el = item.find("link")
                pub_el = item.find("pubDate")
                if title_el is None:
                    continue
                articles.append({
                    "title": title_el.text or "",
                    "url": link_el.text if link_el is not None else "",
                    "published": pub_el.text if pub_el is not None else "",
                })
        except Exception as e:
            logger.warning("News RSS fetch failed for %s: %s", feed_url, e)

    articles = articles[:max_items]

    # Save to anima knowledge dir
    if anima_dir:
        out_path = Path(anima_dir) / "knowledge" / "realtime_news.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps({"fetched_at": datetime.now(timezone.utc).isoformat(), "articles": articles},
                        ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return {"success": True, "count": len(articles), "articles": articles}


# ── Dispatch ──────────────────────────────────────────────


def dispatch(name: str, args: dict[str, Any]) -> Any:
    anima_dir = args.pop("anima_dir", None)

    if name == "tiktok_fetch_trends":
        return fetch_trends(
            keywords=args.get("keywords"),
            anima_dir=anima_dir,
        )

    if name == "tiktok_fetch_news":
        return fetch_news(
            max_items=args.get("max_items", 10),
            anima_dir=anima_dir,
        )

    raise ValueError(f"Unknown tool: {name}")
