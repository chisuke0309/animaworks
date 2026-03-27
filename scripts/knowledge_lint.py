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
ANIMAS = ["cicchi", "kuro", "rue", "sora"]

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
    "x_search", "x_user_tweets",
}

# 廃止済み用語とその説明
DEPRECATED_TERMS: dict[str, tuple[str, str]] = {
    # (パターン, severity, 説明)
    "x_post_request_approval": ("critical", "このツールは存在しない。x_post + cron自動投稿フローに移行済み"),
    "x_post_cancel_pending": ("critical", "このツール名はコードに未実装"),
    "4連投": ("critical", "長文単一投稿（X Premium 25,000文字）に移行済み"),
    "AI・DX領域": ("warning", "ペット・グルーミング/エコ・サステナブルに移行済み（旧ミッション残留の可能性）"),
    "AIトレンド": ("warning", "同上。ペット・グルーミング/エコ・サステナブルに移行済み"),
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
            for term, (severity, desc) in DEPRECATED_TERMS.items():
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
