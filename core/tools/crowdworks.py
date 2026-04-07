# AnimaWorks - Digital Anima Framework
# Copyright (C) 2026 AnimaWorks Authors
# SPDX-License-Identifier: Apache-2.0
#
# This file is part of AnimaWorks core/server, licensed under Apache-2.0.
# See LICENSE for the full license text.

"""CrowdWorks job search tool for AnimaWorks.

Fetches job listings from CrowdWorks public search page.
Data is extracted from the embedded Vue.js JSON in the HTML.
"""
from __future__ import annotations

import argparse
import html as html_mod
import json
import re
import sys
from typing import Any
from urllib.parse import urlencode

import httpx

from core.tools._base import logger

# ── Execution Profile ─────────────────────────────────────

EXECUTION_PROFILE: dict[str, dict[str, object]] = {
    "crowdworks_search": {"expected_seconds": 15, "background_eligible": True},
}

# ── Constants ──────────────────────────────────────────────

BASE_URL = "https://crowdworks.jp/public/jobs/search"
JOB_URL_PREFIX = "https://crowdworks.jp/public/jobs/"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)


# ── Core Functions ─────────────────────────────────────────


def _fetch_page(keywords: str, page: int = 1) -> dict:
    """Fetch a single page of CrowdWorks search results.

    Returns the parsed JSON data from the vue-container data attribute.
    """
    params = {"search[keywords]": keywords}
    if page > 1:
        params["page"] = str(page)

    resp = httpx.get(
        BASE_URL,
        params=params,
        headers={"User-Agent": USER_AGENT},
        timeout=30.0,
        follow_redirects=True,
    )
    resp.raise_for_status()

    m = re.search(r'id="vue-container"[^>]*data="([^"]+)"', resp.text)
    if not m:
        logger.warning("vue-container data attribute not found in CrowdWorks HTML")
        return {}

    raw = html_mod.unescape(m.group(1))
    return json.loads(raw)


def _parse_payment(payment: dict) -> tuple[str, float | None, float | None]:
    """Parse payment dict into (type, min, max)."""
    if "fixed_price_payment" in payment:
        p = payment["fixed_price_payment"]
        return "固定報酬", p.get("min_budget"), p.get("max_budget")
    if "hourly_payment" in payment:
        p = payment["hourly_payment"]
        return "時給", p.get("min_hourly_wage"), p.get("max_hourly_wage")
    if "fixed_price_writing_payment" in payment:
        p = payment["fixed_price_writing_payment"]
        price = p.get("article_price")
        return "タスク", price, price
    if "competition_payment" in payment:
        p = payment["competition_payment"]
        return "コンペ", p.get("price"), p.get("price")
    return "その他", None, None


def _fetch_job_description(job_id: int) -> str:
    """Fetch full job description from individual job page via JSON-LD."""
    try:
        resp = httpx.get(
            f"{JOB_URL_PREFIX}{job_id}",
            headers={"User-Agent": USER_AGENT},
            timeout=30.0,
            follow_redirects=True,
        )
        resp.raise_for_status()
        m = re.search(r'"@type"\s*:\s*"JobPosting".*?"description"\s*:\s*"(.*?)"(?:,|\})', resp.text, re.DOTALL)
        if m:
            raw = m.group(1)
            # unescape JSON string escapes then HTML entities, strip tags
            raw = raw.replace('\\u003c', '<').replace('\\u003e', '>').replace('\\u0026', '&')
            raw = raw.replace('\\"', '"').replace('\\n', '\n').replace('\\/', '/')
            import html as _html
            raw = _html.unescape(raw)
            # strip HTML tags
            clean = re.sub(r'<[^>]+>', '', raw)
            # collapse whitespace
            clean = re.sub(r'\n{3,}', '\n\n', clean).strip()
            return clean
    except Exception as exc:
        logger.warning("Failed to fetch description for job %s: %s", job_id, exc)
    return ""


def _parse_job(entry: dict) -> dict[str, Any]:
    """Parse a single job_offers entry into a flat dict."""
    jo = entry.get("job_offer", {})
    payment = entry.get("payment", {})
    pe = entry.get("entry", {}).get("project_entry", {})
    client = entry.get("client", {})

    pay_type, pay_min, pay_max = _parse_payment(payment)

    job = {
        "id": jo.get("id"),
        "title": jo.get("title", ""),
        "description": _fetch_job_description(jo.get("id")) or jo.get("description_digest", ""),
        "url": f"{JOB_URL_PREFIX}{jo.get('id')}",
        "budget_type": pay_type,
        "budget_min": pay_min,
        "budget_max": pay_max,
        "applicants": pe.get("num_application_conditions", 0),
        "contracts": pe.get("num_contracts", 0),
        "max_contracts": pe.get("project_contract_hope_number"),
        "deadline": jo.get("expired_on", ""),
        "posted_at": jo.get("last_released_at", ""),
        "client_name": client.get("username", ""),
        "client_certified": client.get("is_employer_certification", False),
    }
    score, breakdown = score_job(job)
    job["score"] = score
    job["score_breakdown"] = breakdown
    return job


# ── Scoring ────────────────────────────────────────────────

# chisukeの強みキーワード（スキルマッチ判定用）
_SKILL_KEYWORDS = ("AI", "DX", "SEO", "ディレクション", "Notion", "Python", "IT", "生成AI")
# 専門外ジャンル（上書きで3点）
_OFF_TOPIC_KEYWORDS = ("美容", "看護", "旅行", "コーヒー", "医療", "介護", "ファッション", "料理")
# 継続性キーワード
_CONTINUITY_KEYWORDS = ("継続", "長期", "専属", "月5本", "月10本", "月20本", "月〜本")
# AI利用OKキーワード
_AI_OK_KEYWORDS = ("AI活用", "生成AI", "AIツール", "AI使用OK", "ChatGPT", "Claude")
# 除外キーワード（スコア0）
_EXCLUDE_KEYWORDS = (
    "ミーティング", "web面談", "Web面談", "zoom", "Zoom", "ZOOM",
    "meet", "Meet", "面談", "出社", "通勤", "来社",
    "業務経験", "実務経験", "経験者", "経験必須",
)


def _days_until(deadline: str) -> int | None:
    """Days from today until deadline (YYYY-MM-DD). None if unparseable."""
    if not deadline:
        return None
    try:
        from datetime import date, datetime
        d = datetime.strptime(deadline[:10], "%Y-%m-%d").date()
        return (d - date.today()).days
    except Exception:
        return None


def score_job(job: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Compute おすすめ度 (0-80) for a job.

    Returns (score, breakdown) where breakdown details each component.
    Scoring matches yomi/injection.md spec exactly.
    """
    title = job.get("title", "") or ""
    desc = job.get("description", "") or ""
    text = f"{title} {desc}"
    budget_type = job.get("budget_type", "") or ""
    budget_max = job.get("budget_max") or 0
    applicants = job.get("applicants", 0) or 0
    deadline = job.get("deadline", "") or ""

    # 除外条件チェック
    excluded_by: list[str] = [kw for kw in _EXCLUDE_KEYWORDS if kw in text]
    if excluded_by:
        return 0, {
            "total": 0,
            "excluded": True,
            "excluded_by": excluded_by,
        }

    # 1. 報酬単価 (最大15点)
    if budget_type == "時給":
        if budget_max >= 2000:
            payment_pts = 15
        elif budget_max >= 1500:
            payment_pts = 10
        else:
            payment_pts = 5
    else:  # 固定/タスク/コンペ/その他
        if budget_max >= 30000:
            payment_pts = 15
        elif budget_max >= 10000:
            payment_pts = 10
        elif budget_max >= 5000:
            payment_pts = 7
        elif budget_max >= 2000:
            payment_pts = 4
        else:
            payment_pts = 1

    # 2. 競合少なさ (最大15点)
    if applicants <= 5:
        competition_pts = 15
    elif applicants <= 15:
        competition_pts = 10
    elif applicants <= 30:
        competition_pts = 6
    elif applicants <= 50:
        competition_pts = 3
    else:
        competition_pts = 0

    # 3. スキルマッチ (最大20点)
    off_topic = any(kw in text for kw in _OFF_TOPIC_KEYWORDS)
    if off_topic:
        skill_pts = 3
    else:
        matches = sum(1 for kw in _SKILL_KEYWORDS if kw in text)
        if matches >= 3:
            skill_pts = 20
        elif matches == 2:
            skill_pts = 15
        elif matches == 1:
            skill_pts = 10
        else:
            skill_pts = 5
    if ("AI禁止" in text) or ("人間執筆必須" in text):
        skill_pts = max(0, skill_pts - 5)

    # 4. 継続性 (最大10点)
    continuity_pts = 10 if any(kw in text for kw in _CONTINUITY_KEYWORDS) else 0

    # 5. 応募期限余裕 (最大10点)
    days = _days_until(deadline)
    if days is None:
        deadline_pts = 0
    elif days >= 10:
        deadline_pts = 10
    elif days >= 5:
        deadline_pts = 6
    elif days >= 2:
        deadline_pts = 3
    else:
        deadline_pts = 0

    # 6. AI利用OK (最大10点)
    ai_ok = any(kw in text for kw in _AI_OK_KEYWORDS) and "AI禁止" not in text
    ai_pts = 10 if ai_ok else 0

    total = (
        payment_pts + competition_pts + skill_pts
        + continuity_pts + deadline_pts + ai_pts
    )
    breakdown = {
        "total": total,
        "excluded": False,
        "payment": payment_pts,
        "competition": competition_pts,
        "skill": skill_pts,
        "continuity": continuity_pts,
        "deadline": deadline_pts,
        "ai_ok": ai_pts,
    }
    return total, breakdown


def score_level(score: int) -> str:
    """Return ★ level string for a score."""
    if score == 0:
        return "除外"
    if score >= 55:
        return "★★★"
    if score >= 40:
        return "★★"
    return "★"


def search_jobs(
    keywords: str,
    max_pages: int = 1,
    min_budget: float | None = None,
) -> list[dict[str, Any]]:
    """Search CrowdWorks for jobs matching keywords.

    Args:
        keywords: Search query (e.g. "記事作成 SEO").
        max_pages: Maximum number of pages to fetch (1-5).
        min_budget: Minimum budget filter (applied client-side).

    Returns:
        List of parsed job dicts.
    """
    max_pages = min(max(max_pages, 1), 5)
    all_jobs: list[dict[str, Any]] = []

    for page in range(1, max_pages + 1):
        try:
            data = _fetch_page(keywords, page)
        except Exception as exc:
            logger.error("CrowdWorks fetch page %d failed: %s", page, exc)
            break

        sr = data.get("searchResult", {})
        offers = sr.get("job_offers", [])
        if not offers:
            break

        # Fetch descriptions in parallel
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            jobs = list(executor.map(_parse_job, offers))
        all_jobs.extend(jobs)

        # Check if more pages exist
        page_info = sr.get("page", {})
        if page >= page_info.get("total_page", 1):
            break

    # Client-side filter
    if min_budget is not None:
        all_jobs = [
            j for j in all_jobs
            if (j["budget_max"] or 0) >= min_budget
        ]

    logger.info(
        "CrowdWorks search '%s': %d jobs found (pages: %d)",
        keywords, len(all_jobs), max_pages,
    )
    return all_jobs


def format_results(jobs: list[dict[str, Any]]) -> str:
    """Format job results as human-readable text."""
    if not jobs:
        return "案件が見つかりませんでした。"

    lines: list[str] = []
    for i, j in enumerate(jobs, 1):
        budget = ""
        if j["budget_min"] and j["budget_max"]:
            budget = f"¥{j['budget_min']:,.0f}〜¥{j['budget_max']:,.0f}"
        elif j["budget_max"]:
            budget = f"〜¥{j['budget_max']:,.0f}"
        elif j["budget_min"]:
            budget = f"¥{j['budget_min']:,.0f}〜"
        else:
            budget = "要相談"

        cert = " [認定]" if j["client_certified"] else ""
        lines.append(f"{i}. {j['title']}")
        lines.append(f"   {j['budget_type']} {budget} | 応募{j['applicants']}人 | 〆{j['deadline']}")
        lines.append(f"   {j['client_name']}{cert} | {j['url']}")
        lines.append("")

    return "\n".join(lines)


# ── Anthropic tool_use schema ──────────────────────────────


def get_tool_schemas() -> list[dict]:
    """Return Anthropic tool_use schemas for the crowdworks tools."""
    return [
        {
            "name": "crowdworks_search",
            "description": (
                "CrowdWorksで案件を検索する。キーワードで検索し、"
                "案件名・報酬・応募数・期限・クライアント情報を取得する。"
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "string",
                        "description": "検索キーワード（例: '記事作成 SEO'）",
                    },
                    "max_pages": {
                        "type": "integer",
                        "description": "取得ページ数（1-5、デフォルト1、1ページ=約50件）",
                        "default": 1,
                    },
                    "min_budget": {
                        "type": "number",
                        "description": "最低報酬フィルタ（円）。この金額以上の案件のみ返す。",
                    },
                },
                "required": ["keywords"],
            },
        },
    ]


# ── Dispatch ──────────────────────────────────────────


def dispatch(name: str, args: dict[str, Any]) -> Any:
    """Dispatch a tool call by schema name."""
    if name == "crowdworks_search":
        args.pop("anima_dir", None)
        if "max_pages" in args:
            try:
                args["max_pages"] = int(args["max_pages"])
            except (TypeError, ValueError):
                args["max_pages"] = 1
        if "min_budget" in args and args["min_budget"] is not None:
            try:
                args["min_budget"] = float(args["min_budget"])
            except (TypeError, ValueError):
                args.pop("min_budget", None)
        return search_jobs(**args)
    raise ValueError(f"Unknown tool: {name}")


# ── CLI entry point ────────────────────────────────────


def cli_main(argv: list[str] | None = None) -> None:
    """CLI entry point for crowdworks tool."""
    parser = argparse.ArgumentParser(
        description="Search CrowdWorks job listings",
    )
    parser.add_argument("keywords", help="Search keywords (e.g. '記事作成 SEO')")
    parser.add_argument(
        "-p", "--pages",
        type=int,
        default=1,
        help="Number of pages to fetch (1-5, default: 1)",
    )
    parser.add_argument(
        "-m", "--min-budget",
        type=float,
        default=None,
        help="Minimum budget filter (yen)",
    )
    parser.add_argument(
        "-j", "--json",
        action="store_true",
        help="Output as JSON",
    )

    args = parser.parse_args(argv)

    results = search_jobs(
        keywords=args.keywords,
        max_pages=args.pages,
        min_budget=args.min_budget,
    )

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(format_results(results))
