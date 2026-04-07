#!/usr/bin/env python3
"""knowledge_lint.py — AnimaWorks ナレッジ横断整合性チェッカー

全Animaの設定・ナレッジファイルをスキャンし、矛盾・廃止語・不整合を検出する。
handoff コマンドから自動実行され、結果をLLMが解釈する。

Usage:
    uv run python scripts/knowledge_lint.py [--json] [--anima NAME]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

# ── 定数 ──────────────────────────────────────────────

ANIMA_BASE = Path(os.path.expanduser("~/.animaworks/animas"))
SHARED_BASE = Path(os.path.expanduser("~/.animaworks/shared"))

def _load_anima_names() -> list[str]:
    """config.json の animas セクションからAnima名一覧を動的に取得する。
    config.json が存在しない場合はフォールバックリストを返す。
    """
    config_path = Path(os.path.expanduser("~/.animaworks/config.json"))
    if config_path.exists():
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
        # unit が null（human/ops）のエントリを除外し、実Animaのみ返す
        return [
            name for name, val in cfg.get("animas", {}).items()
            if val.get("unit") is not None
        ]
    return ["cicchi", "kuro", "rue", "sora", "hana", "maru", "chiro", "tama"]

ANIMAS = _load_anima_names()

# スキャン対象（top-level md + knowledge/ + procedures/）
TOP_LEVEL_FILES = ["identity.md", "injection.md", "cron.md", "permissions.md"]

# コードベースから抽出した正規ツール名一覧（2026-03-27時点）
VALID_TOOL_NAMES = {
    "add_task", "archive_memory_file", "aws_ecs_status", "aws_error_logs",
    "aws_metrics", "call_human", "chatwork_mentions", "chatwork_messages",
    "chatwork_rooms", "chatwork_search", "chatwork_send", "chatwork_sync",
    "chatwork_unreplied", "check_permissions", "create_anima", "create_skill",
    "delegate_task", "disable_subordinate", "discover_tools", "edit_file",
    "enable_subordinate", "execute_command", "generate_3d_model",
    "generate_animations", "generate_bustup", "generate_character_assets",
    "generate_chibi", "generate_fullbody", "generate_rigged_model",
    "github_create_issue", "github_create_pr", "github_list_issues",
    "github_list_prs", "gmail_draft", "gmail_read_body", "gmail_unread",
    "list_directory", "list_tasks", "local_llm_chat", "local_llm_generate",
    "local_llm_models", "local_llm_status", "org_dashboard",
    "ping_subordinate", "post_channel", "read_channel", "read_dm_history",
    "read_file", "read_memory_file", "read_subordinate_state",
    "refresh_tools", "report_knowledge_outcome", "report_procedure_outcome",
    "restart_subordinate", "search_code", "search_memory", "send_message",
    "set_subordinate_model", "share_tool", "skill", "slack_channels",
    "slack_messages", "slack_search", "slack_send", "slack_unreplied",
    "task_tracker", "transcribe_audio", "update_task", "web_fetch",
    "web_search", "write_file", "write_memory_file", "x_post",
    "x_post_thread", "x_post_save_pending", "x_post_execute_pending",
    "x_search", "x_user_tweets", "x_post_update_engagement",
    "x_like", "x_reply", "x_quote",
    "tiktok_analytics",
    # tiktok_analytics のアクション名（dispatch経由で呼ぶ）
    "tiktok_scrape_engagement", "tiktok_get_performance", "tiktok_record_engagement",
}

# 廃止済み用語とその説明
# 形式: term -> (severity, 説明, applicable_animas or None)
# applicable_animas=None のとき全Anima対象。リストを指定するとそのAnima配下のみ対象。
DEPRECATED_TERMS: dict[str, tuple[str, str, list[str] | None]] = {
    "x_post_request_approval": ("critical", "このツールは存在しない。x_post + cron自動投稿フローに移行済み", None),
    "x_post_cancel_pending": ("critical", "このツール名はコードに未実装", None),
    "4連投": ("critical", "長文単一投稿（X Premium 25,000文字）に移行済み", None),
    # X事業部（cicchi/rue/kuro/sora/hana）のみ対象。TikTok事業部（maru/chiro/tama）はAI系ニッチを継続中。
    "AI・DX領域": ("warning", "X事業部はペット・グルーミング/エコ・サステナブルに移行済み（旧ミッション残留の可能性）", ["cicchi", "rue", "kuro", "sora", "hana"]),
    "AIトレンド": ("warning", "X事業部は同上。ペット・グルーミング/エコ・サステナブルに移行済み", ["cicchi", "rue", "kuro", "sora", "hana"]),
}

# ── データ構造 ─────────────────────────────────────────

@dataclass
class Issue:
    severity: str  # critical, warning, info
    category: str  # char_limit, tool_name, format_rule, deprecated_term, workflow
    message: str
    files: list[dict] = field(default_factory=list)
    suggestion: str = ""


@dataclass
class LintReport:
    timestamp: str = ""
    version: str = "1.0.0"
    issues: list[Issue] = field(default_factory=list)
    checked_files: list[str] = field(default_factory=list)

    def add(self, issue: Issue):
        self.issues.append(issue)

    @property
    def summary(self) -> dict:
        counts = {"critical": 0, "warning": 0, "info": 0}
        by_cat: dict[str, int] = {}
        for i in self.issues:
            counts[i.severity] = counts.get(i.severity, 0) + 1
            by_cat[i.category] = by_cat.get(i.category, 0) + 1
        return {
            "critical": counts["critical"],
            "warning": counts["warning"],
            "info": counts["info"],
            "total": len(self.issues),
            "by_category": by_cat,
        }

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "version": self.version,
            "issues": [asdict(i) for i in self.issues],
            "summary": self.summary,
            "checked_files": self.checked_files,
            "files_scanned": len(self.checked_files),
        }


# ── ファイル収集 ───────────────────────────────────────

def collect_files(anima_filter: Optional[str] = None) -> list[tuple[str, str, str]]:
    """(path, content, source) のリストを返す。source は anima名 or 'shared'。"""
    results = []
    animas = [anima_filter] if anima_filter else ANIMAS

    for anima in animas:
        base = ANIMA_BASE / anima
        if not base.exists():
            continue

        # top-level md
        for fname in TOP_LEVEL_FILES:
            fpath = base / fname
            if fpath.exists():
                results.append((str(fpath), fpath.read_text(encoding="utf-8", errors="replace"), anima))

        # knowledge/*.md
        kdir = base / "knowledge"
        if kdir.exists():
            for md in sorted(kdir.glob("*.md")):
                results.append((str(md), md.read_text(encoding="utf-8", errors="replace"), anima))

        # procedures/*.md
        pdir = base / "procedures"
        if pdir.exists():
            for md in sorted(pdir.glob("*.md")):
                results.append((str(md), md.read_text(encoding="utf-8", errors="replace"), anima))

    # shared pipelines
    if not anima_filter:
        pipelines = SHARED_BASE / "pipelines"
        if pipelines.exists():
            for md in sorted(pipelines.glob("*.md")):
                results.append((str(md), md.read_text(encoding="utf-8", errors="replace"), "shared"))

    return results


# ── チェッカー ─────────────────────────────────────────

def check_char_limits(files: list[tuple[str, str, str]], report: LintReport):
    """文字数制限の不一致を検出。"""
    PATTERNS = [
        re.compile(r'(\d[\d,_]*)\s*文字'),
        re.compile(r'(\d[\d,_]*)\s*字以内'),
        re.compile(r'最大\s*(\d[\d,_]*)'),
        re.compile(r'(\d[\d,_]*)\s*char', re.IGNORECASE),
        re.compile(r'MAX_CHARS\s*=\s*(\d+)'),
    ]

    # 280をスレッド文脈で使っている場合はOK
    THREAD_CONTEXT = re.compile(r'スレッド|thread|個別|per.?tweet|各ツイート', re.IGNORECASE)
    # 単一投稿の文脈
    SINGLE_CONTEXT = re.compile(r'Premium|長文|単一投稿|single.?post|上限|制限|以内', re.IGNORECASE)

    for path, content, source in files:
        lines = content.split("\n")
        for line_no, line in enumerate(lines, 1):
            for pat in PATTERNS:
                for m in pat.finditer(line):
                    raw = m.group(1).replace(",", "").replace("_", "")
                    try:
                        num = int(raw)
                    except ValueError:
                        continue
                    if num < 100 or num > 100000:
                        continue  # 無関係な数値

                    # 280を非スレッド文脈で使用 → 古い制限の可能性
                    if num == 280:
                        context_window = content[max(0, m.start() - 200):m.end() + 200]
                        if not THREAD_CONTEXT.search(context_window):
                            report.add(Issue(
                                severity="warning",
                                category="char_limit",
                                message=f"280文字制限の記述あり（スレッド文脈なし）。X Premium では25,000文字が上限",
                                files=[{"path": path, "line": line_no, "snippet": line.strip()[:100]}],
                                suggestion="スレッド個別ツイートの文脈なら明記する。単一投稿なら25,000文字に修正",
                            ))


def check_tool_names(files: list[tuple[str, str, str]], report: LintReport):
    """存在しないツール名の参照を検出。"""
    # バッククォートで囲まれたツール名風の文字列を抽出
    TOOL_REF = re.compile(r'`([a-z][a-z0-9_]+)`')
    # x_post_ プレフィックスは特に注意
    X_POST_REF = re.compile(r'\b(x_post_[a-z_]+)\b')

    for path, content, source in files:
        lines = content.split("\n")
        for line_no, line in enumerate(lines, 1):
            # バージョン履歴行や将来実装NOTE行はスキップ
            stripped = line.strip()
            if stripped.startswith("- v") and ("→" in line or "に修正" in line):
                continue
            if "将来的に" in line or "実装予定" in line:
                continue
            # バッククォート内のツール名
            for m in TOOL_REF.finditer(line):
                name = m.group(1)
                # ツール名っぽいもの（アンダースコア含む）のみチェック
                if "_" not in name:
                    continue
                if name in VALID_TOOL_NAMES:
                    continue
                # 既知の非ツール名をスキップ（変数名、MCP名、ファイル名、ステータス名など）
                if name.startswith(("is_", "has_", "get_", "set_", "max_", "min_", "mcp__")):
                    continue
                # ファイル名（.md, .json等が後続する）はスキップ
                if re.search(rf'`{re.escape(name)}`\s*\.\w+', line) or f"{name}.md" in line or f"{name}.json" in line:
                    continue
                # 既知の非ツール名をホワイトリストでスキップ
                NON_TOOL_NAMES = {
                    "x_post_log", "activity_log", "topic_label", "kuro_done",
                    "generate_tiktok_image", "portrait_4_3", "tiktok_prompt_templates",
                    "test3_step2_writing", "index_meta", "x_post_test3",
                    "from_person", "to_person", "in_reply_to_tweet_id",
                    "quote_tweet_id", "likes_per_session", "replies_per_session",
                    "quotes_per_session", "tiktok_body", "overlay_texts",
                }
                if name in NON_TOOL_NAMES:
                    continue
                report.add(Issue(
                    severity="critical",
                    category="tool_name",
                    message=f"存在しないツール名 `{name}` を参照",
                    files=[{"path": path, "line": line_no, "snippet": line.strip()[:100]}],
                    suggestion=f"正しいツール名に修正するか、記述を削除する",
                ))

            # x_post_ プレフィックスの未登録ツール
            for m in X_POST_REF.finditer(line):
                name = m.group(1)
                if name in VALID_TOOL_NAMES:
                    continue
                # バッククォートチェックと重複する場合スキップ
                if f"`{name}`" in line:
                    continue
                # ファイル名参照はスキップ（x_post_log.md 等）
                if f"{name}.md" in line or f"{name}.json" in line:
                    continue
                report.add(Issue(
                    severity="critical",
                    category="tool_name",
                    message=f"未実装のツール名 `{name}` を参照",
                    files=[{"path": path, "line": line_no, "snippet": line.strip()[:100]}],
                    suggestion=f"`{name}` はコードベースに存在しない。正しいツール名に修正する",
                ))


def check_format_rules(files: list[tuple[str, str, str]], report: LintReport):
    """投稿形式の矛盾を検出（4連投 vs 長文単一投稿）。"""
    THREAD_POSITIVE = re.compile(r'4連投|スレッド構成|複数ツイート|thread.?format', re.IGNORECASE)
    SINGLE_POSITIVE = re.compile(r'長文単一投稿|single.?post|1投稿形式|スレッド分割不要', re.IGNORECASE)
    # 「スレッド禁止」は単一投稿を支持する記述なので除外（THREAD_POSITIVEに含めない）
    THREAD_NEGATIVE = re.compile(r'スレッド.*禁止|4連投.*禁止|スレッド.*不要', re.IGNORECASE)

    for path, content, source in files:
        lines = content.split("\n")
        has_thread = []
        has_single = []

        for line_no, line in enumerate(lines, 1):
            # 「禁止」「不要」文脈のスレッド言及はスキップ
            if THREAD_POSITIVE.search(line) and not THREAD_NEGATIVE.search(line):
                # バージョン履歴行もスキップ
                if line.strip().startswith("- v") or "→" in line and "に統一" in line:
                    continue
                has_thread.append((line_no, line.strip()[:80]))
            if SINGLE_POSITIVE.search(line):
                has_single.append((line_no, line.strip()[:80]))

        # 同一ファイル内で矛盾
        if has_thread and has_single:
            report.add(Issue(
                severity="critical",
                category="format_rule",
                message=f"同一ファイル内でスレッド形式と単一投稿形式の両方を記述",
                files=[
                    {"path": path, "line": has_thread[0][0], "snippet": has_thread[0][1]},
                    {"path": path, "line": has_single[0][0], "snippet": has_single[0][1]},
                ],
                suggestion="現行ルール（長文単一投稿）に統一する",
            ))


def check_deprecated_terms(files: list[tuple[str, str, str]], report: LintReport):
    """廃止済み用語の残存を検出。"""
    for path, content, source in files:
        lines = content.split("\n")
        for line_no, line in enumerate(lines, 1):
            for term, (severity, desc, applicable_animas) in DEPRECATED_TERMS.items():
                # applicable_animasが指定されている場合、対象Animaのファイルのみチェック
                if applicable_animas is not None:
                    if not any(f"/animas/{a}/" in path for a in applicable_animas):
                        continue
                if term in line:
                    # コメント行や「廃止」の説明として言及している場合はスキップ
                    if "廃止" in line or "旧:" in line or "deprecated" in line.lower():
                        continue
                    # 「禁止」の文脈（例: 「4連投は禁止」）もスキップ
                    if "禁止" in line or "使わない" in line or "不要" in line:
                        continue
                    # バージョン履歴行（変更記録）はスキップ
                    if line.strip().startswith("- v") and ("→" in line or "に修正" in line or "に統一" in line):
                        continue
                    # 将来実装のNOTE行はスキップ
                    if "将来的に" in line or "実装予定" in line:
                        continue
                    report.add(Issue(
                        severity=severity,
                        category="deprecated_term",
                        message=f"廃止済み用語 `{term}` が残存: {desc}",
                        files=[{"path": path, "line": line_no, "snippet": line.strip()[:100]}],
                        suggestion=f"この用語を削除または現行の表現に更新する",
                    ))


def _parse_goals_md() -> dict:
    """goals.mdを解析してunit別の要件を返す。

    Returns:
        {
            "x": {
                "label": "X事業部",
                "lead": "cicchi",
                "post_hours": [8, 17],
                "genre_keywords": ["ペット", "グルーミング", ...],
                "forbidden_themes": ["副業", ...],
                "weekly_check": {"anima": "rue", "hour": 8},
            },
            "tiktok": { ... },
        }
    """
    goals_path = Path(os.path.expanduser("~/.animaworks/common_knowledge/organization/goals.md"))
    if not goals_path.exists():
        return {}

    content = goals_path.read_text(encoding="utf-8")
    units: dict = {}

    # <!-- unit:xxx --> マーカーでセクション分割
    unit_pattern = re.compile(r'<!-- unit:(\w+) -->(.*?)(?=<!-- unit:|\Z)', re.DOTALL)
    for m in unit_pattern.finditer(content):
        unit_id = m.group(1)
        sec = m.group(2)

        # ラベル（## X事業部 / ## TikTok事業部）
        label_m = re.search(r'^## (.+)', sec, re.MULTILINE)
        label = label_m.group(1).strip() if label_m else unit_id

        # 投稿頻度行から時刻を抽出: "1日2回（朝8時・夕17時）"
        post_hours: list[int] = []
        for freq_line in sec.split('\n'):
            if '投稿頻度' in freq_line or '投稿時刻' in freq_line:
                post_hours = [int(h) for h in re.findall(r'(\d+)時', freq_line) if 0 <= int(h) <= 23]
                break

        # ジャンル行からキーワードを抽出
        genre_keywords: list[str] = []
        for line in sec.split('\n'):
            if 'ジャンル' in line and ':' in line:
                raw = line.split(':', 1)[1].strip()
                # マークダウン強調を除去
                raw = re.sub(r'\*\*|\`', '', raw)
                genre_keywords = [k.strip() for k in re.split(r'[/・＋、,\s]+', raw) if k.strip()]
                break

        # 禁止テーマ行から抽出
        forbidden_themes: list[str] = []
        for line in sec.split('\n'):
            if '禁止テーマ' in line and ':' in line:
                raw = line.split(':', 1)[1].strip()
                raw = re.sub(r'\*\*|\`', '', raw)
                # "副業・稼ぎ方系（AI副業、月○万等）" のような形式を整形
                raw = re.sub(r'（[^）]*）', '', raw)
                forbidden_themes = [k.strip() for k in re.split(r'[/・、,\s]+', raw) if k.strip()]
                break

        # 週次チェック行: "rueが毎週月曜8時に確認"
        weekly_check: dict | None = None
        for line in sec.split('\n'):
            if '週次チェック' in line:
                a_m = re.search(r'(\w+)が毎週', line)
                h_m = re.search(r'(\d+)時', line)
                if a_m and h_m:
                    weekly_check = {"anima": a_m.group(1), "hour": int(h_m.group(1))}
                    break

        units[unit_id] = {
            "label": label,
            "post_hours": post_hours,
            "genre_keywords": genre_keywords,
            "forbidden_themes": forbidden_themes,
            "weekly_check": weekly_check,
        }

    return units


def _parse_cron_schedules(cron_path: Path) -> list[dict]:
    """cron.mdから schedule: エントリを解析する。"""
    if not cron_path.exists():
        return []
    schedules = []
    for m in re.finditer(
        r'^schedule:\s*(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)',
        cron_path.read_text(encoding="utf-8"),
        re.MULTILINE,
    ):
        minute, hour, dom, month, dow = m.groups()
        schedules.append({"minute": minute, "hour": hour, "dom": dom, "month": month, "dow": dow})
    return schedules


def _has_hour(schedules: list[dict], hour: int) -> bool:
    """指定時刻（時）のスケジュールが存在するか。"""
    return any(s["hour"] == str(hour) for s in schedules)


def _has_weekly_at_hour(schedules: list[dict], hour: int) -> bool:
    """指定時刻の月曜定期スケジュールが存在するか。"""
    for s in schedules:
        if s["hour"] == str(hour):
            # dow が 1 または 1 を含むカンマ区切り
            dow_parts = s["dow"].replace(" ", "").split(",")
            if "1" in dow_parts or s["dow"] == "*":
                return True
    return False


def _load_unit_config() -> dict:
    """config.json の unit フィールドから unit→anima一覧・リードを動的に構築する。

    Returns:
        {
            "x":      {"members": ["cicchi", "rue", ...], "lead": "cicchi"},
            "tiktok": {"members": ["maru", "chiro", "tama"], "lead": "maru"},
        }
    """
    config_path = Path(os.path.expanduser("~/.animaworks/config.json"))
    if not config_path.exists():
        return {}

    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    animas = cfg.get("animas", {})

    units: dict = {}
    for name, val in animas.items():
        unit_id = val.get("unit")
        if not unit_id:
            continue
        if unit_id not in units:
            units[unit_id] = {"members": [], "lead": None}
        units[unit_id]["members"].append(name)
        # supervisor が null（＝自律リーダー）かつ unit が一致 → リード
        if val.get("supervisor") is None:
            units[unit_id]["lead"] = name

    return units


def check_org_goals_alignment(_files: list[tuple[str, str, str]], report: LintReport):
    """組織目標(goals.md)と各Animaの設定ファイルの整合性チェック。

    チェック項目:
      1. 必須投稿スケジュール — goals.mdの投稿時刻がリードAnimaのcron.mdに存在するか
      2. 週次チェックcron    — goals.md指定の担当Animaに月曜スケジュールがあるか
      3. ジャンルキーワード  — goals.mdのジャンルがリードAnimaのinjection.mdに反映されているか
      4. 禁止テーマの明記   — goals.mdの禁止テーマがinjection/identity.mdに記載されているか
    """
    units = _parse_goals_md()
    if not units:
        return  # goals.md が存在しない場合はスキップ

    # config.json からunit構成を動的に取得
    unit_config = _load_unit_config()

    for unit_id, unit in units.items():
        label = unit["label"]
        # リードAnimaは config.json の unit フィールド + supervisor=null から自動解決
        lead = unit_config.get(unit_id, {}).get("lead")

        # ── 1. 投稿スケジュールチェック ──────────────────────────────
        if lead and unit["post_hours"]:
            cron_path = ANIMA_BASE / lead / "cron.md"
            schedules = _parse_cron_schedules(cron_path)
            for hour in unit["post_hours"]:
                if not _has_hour(schedules, hour):
                    report.add(Issue(
                        severity="warning",
                        category="org_alignment",
                        message=f"[{label}] goals.md必須の{hour}時投稿が {lead}/cron.md に未定義",
                        files=[{"path": str(cron_path), "line": 0,
                                "snippet": f"schedule: 0 {hour} * * * が見当たらない"}],
                        suggestion=f"goals.mdの投稿頻度に合わせて cron.md に `schedule: 0 {hour} * * *` を追加する",
                    ))

        # ── 2. 週次チェックcronチェック ──────────────────────────────
        wc = unit.get("weekly_check")
        if wc:
            wc_anima, wc_hour = wc["anima"], wc["hour"]
            wc_cron = ANIMA_BASE / wc_anima / "cron.md"
            wc_schedules = _parse_cron_schedules(wc_cron)
            if not _has_weekly_at_hour(wc_schedules, wc_hour):
                report.add(Issue(
                    severity="warning",
                    category="org_alignment",
                    message=f"[{label}] goals.md指定の週次チェック（{wc_anima} 月曜{wc_hour}時）が cron.md に未定義",
                    files=[{"path": str(wc_cron), "line": 0,
                            "snippet": f"schedule: 0 {wc_hour} * * 1 が見当たらない"}],
                    suggestion=f"{wc_anima}/cron.md に `schedule: 0 {wc_hour} * * 1` を追加する",
                ))

        # ── 3. ジャンルキーワード整合チェック ────────────────────────
        # injection.md + identity.md の両方を検索対象とする
        if lead and unit["genre_keywords"]:
            check_for_genre = [
                ANIMA_BASE / lead / "injection.md",
                ANIMA_BASE / lead / "identity.md",
            ]
            genre_combined = " ".join(
                p.read_text(encoding="utf-8") for p in check_for_genre if p.exists()
            )
            found = [k for k in unit["genre_keywords"] if k in genre_combined]
            if not found:
                kws = "、".join(unit["genre_keywords"][:4])
                injection_path = ANIMA_BASE / lead / "injection.md"
                report.add(Issue(
                    severity="warning",
                    category="org_alignment",
                    message=f"[{label}] goals.mdのジャンルキーワード（{kws}…）が {lead}/injection.md・identity.md に見当たらない",
                    files=[{"path": str(injection_path), "line": 0,
                            "snippet": f"期待キーワード: {kws}"}],
                    suggestion="injection.mdまたはidentity.mdにジャンル・ニッチ情報を明記する",
                ))

        # ── 4. 禁止テーマの明記チェック ──────────────────────────────
        if lead and unit["forbidden_themes"]:
            check_paths = [
                ANIMA_BASE / lead / "injection.md",
                ANIMA_BASE / lead / "identity.md",
            ]
            found_prohibition = False
            for cp in check_paths:
                if not cp.exists():
                    continue
                cp_content = cp.read_text(encoding="utf-8")
                if any(t in cp_content for t in unit["forbidden_themes"]) and \
                   any(w in cp_content for w in ["禁止", "NG", "やらない", "扱わない"]):
                    found_prohibition = True
                    break
            if not found_prohibition:
                themes = "、".join(unit["forbidden_themes"][:3])
                report.add(Issue(
                    severity="info",
                    category="org_alignment",
                    message=f"[{label}] goals.mdの禁止テーマ（{themes}）の明示的禁止ルールが injection/identity.md に未記載",
                    files=[{"path": str(ANIMA_BASE / lead / "injection.md"), "line": 0,
                            "snippet": f"禁止テーマ: {themes}"}],
                    suggestion="injection.mdまたはidentity.mdに禁止テーマを明記する",
                ))


def check_workflow_consistency(files: list[tuple[str, str, str]], report: LintReport):
    """ワークフロー役割割り当ての不整合を検出。"""
    ROLE_ACTIONS = {
        "rue": re.compile(r'rue\s*(?:が|は|に|→)\s*(?:ニッチ|調査|リサーチ|トレンド)', re.IGNORECASE),
        "kuro": re.compile(r'kuro\s*(?:が|は|に|→)\s*(?:コンテンツ|制作|ライト|リライト|長文|記事)', re.IGNORECASE),
        "sora": re.compile(r'sora\s*(?:が|は|に|→)\s*(?:画像|ビジュアル|生成|イラスト)', re.IGNORECASE),
        "cicchi": re.compile(r'cicchi\s*(?:が|は|に|→)\s*(?:委任|オーケスト|確認|承認|投稿|save)', re.IGNORECASE),
    }

    # 各ファイルで検出された役割記述を収集
    role_mentions: dict[str, list[tuple[str, int, str]]] = {a: [] for a in ANIMAS}

    for path, content, source in files:
        lines = content.split("\n")
        for line_no, line in enumerate(lines, 1):
            for anima, pat in ROLE_ACTIONS.items():
                if pat.search(line):
                    role_mentions[anima].append((path, line_no, line.strip()[:80]))

    # 今のところは情報収集のみ（矛盾検出は将来拡張）
    # rueのアクションに「コンテンツ制作」が含まれていたら矛盾など
    for path, content, source in files:
        # rueがコンテンツ制作をしている記述
        if re.search(r'rue\s*(?:が|は|に|→)\s*(?:コンテンツ|制作|ライト|リライト)', content):
            lines = content.split("\n")
            for line_no, line in enumerate(lines, 1):
                if re.search(r'rue\s*(?:が|は|に|→)\s*(?:コンテンツ|制作|ライト|リライト)', line):
                    report.add(Issue(
                        severity="warning",
                        category="workflow",
                        message="rueにコンテンツ制作の役割が記述されている（rueは調査担当、制作はkuro）",
                        files=[{"path": path, "line": line_no, "snippet": line.strip()[:80]}],
                        suggestion="役割記述をkuroに修正する",
                    ))
                    break

        # kuroが調査をしている記述
        if re.search(r'kuro\s*(?:が|は|に|→)\s*(?:ニッチ|調査|リサーチ|トレンド)', content):
            lines = content.split("\n")
            for line_no, line in enumerate(lines, 1):
                if re.search(r'kuro\s*(?:が|は|に|→)\s*(?:ニッチ|調査|リサーチ|トレンド)', line):
                    report.add(Issue(
                        severity="warning",
                        category="workflow",
                        message="kuroに調査の役割が記述されている（kuroはコンテンツ制作担当、調査はrue）",
                        files=[{"path": path, "line": line_no, "snippet": line.strip()[:80]}],
                        suggestion="役割記述をrueに修正する",
                    ))
                    break


# ── 重複排除 ───────────────────────────────────────────

def deduplicate_issues(issues: list[Issue]) -> list[Issue]:
    """同一ファイル・同一行の重複を除去。同じ行で複数カテゴリが検出された場合はcriticalを優先。"""
    # file:line をキーにして、最も重要なissueだけを残す
    by_location: dict[str, Issue] = {}
    severity_rank = {"critical": 0, "warning": 1, "info": 2}

    for issue in issues:
        for f in issue.files:
            loc_key = f"{f['path']}:{f.get('line', '?')}"
            if loc_key in by_location:
                existing = by_location[loc_key]
                # 同じ severity なら category が違えば両方残す（別の問題）
                # ただし tool_name と deprecated_term が同じ行なら統合
                if {existing.category, issue.category} == {"tool_name", "deprecated_term"}:
                    # tool_name の方を優先（より具体的）
                    if issue.category == "tool_name":
                        by_location[loc_key] = issue
                    continue
                elif severity_rank.get(issue.severity, 9) < severity_rank.get(existing.severity, 9):
                    by_location[loc_key] = issue
            else:
                by_location[loc_key] = issue

    # 重複排除した結果を返す（元のissueリストから、by_locationに残ったものだけ）
    seen_ids: set[int] = set()
    result = []
    for issue in by_location.values():
        if id(issue) not in seen_ids:
            seen_ids.add(id(issue))
            result.append(issue)
    return result


# ── メイン ─────────────────────────────────────────────

def run_lint(anima_filter: Optional[str] = None) -> LintReport:
    jst = timezone(timedelta(hours=9))
    report = LintReport(timestamp=datetime.now(jst).isoformat())

    files = collect_files(anima_filter)
    report.checked_files = [f[0] for f in files]

    check_char_limits(files, report)
    check_tool_names(files, report)
    check_format_rules(files, report)
    check_deprecated_terms(files, report)
    check_workflow_consistency(files, report)
    check_org_goals_alignment(files, report)

    report.issues = deduplicate_issues(report.issues)

    # severity順にソート (critical > warning > info)
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    report.issues.sort(key=lambda i: severity_order.get(i.severity, 9))

    return report


def format_human_readable(report: LintReport) -> str:
    """人間が読みやすい形式で出力。"""
    lines = []
    s = report.summary
    lines.append(f"Knowledge Lint Report ({report.timestamp})")
    lines.append(f"{'=' * 60}")
    lines.append(f"Files scanned: {len(report.checked_files)}")
    lines.append(f"Issues: critical={s['critical']}, warning={s['warning']}, info={s['info']}")
    lines.append("")

    if not report.issues:
        lines.append("No issues found.")
        return "\n".join(lines)

    for i, issue in enumerate(report.issues, 1):
        icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(issue.severity, "⚪")
        lines.append(f"{icon} [{issue.severity.upper()}] {issue.category}")
        lines.append(f"   {issue.message}")
        for f in issue.files:
            path_short = f["path"].replace(str(ANIMA_BASE) + "/", "").replace(str(SHARED_BASE) + "/", "shared/")
            lines.append(f"   → {path_short}:{f.get('line', '?')}")
            if f.get("snippet"):
                lines.append(f"     | {f['snippet']}")
        if issue.suggestion:
            lines.append(f"   💡 {issue.suggestion}")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="AnimaWorks Knowledge Lint")
    parser.add_argument("--json", action="store_true", help="JSON出力")
    parser.add_argument("--anima", type=str, help="特定のAnimaのみチェック")
    args = parser.parse_args()

    report = run_lint(anima_filter=args.anima)

    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(format_human_readable(report))

    # exit code: critical があれば 1
    sys.exit(1 if report.summary["critical"] > 0 else 0)


if __name__ == "__main__":
    main()
