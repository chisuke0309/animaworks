# AnimaWorks - Digital Anima Framework
# Copyright (C) 2026 AnimaWorks Authors
# SPDX-License-Identifier: Apache-2.0
#
# This file is part of AnimaWorks core/server, licensed under Apache-2.0.
# See LICENSE for the full license text.

"""Notion API tool for AnimaWorks.

Provides database query, page creation, and page update via Notion API.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import httpx

from core.tools._base import get_credential, logger

# ── Execution Profile ─────────────────────────────────────

EXECUTION_PROFILE: dict[str, dict[str, object]] = {
    "notion_query_database": {"expected_seconds": 10, "background_eligible": False},
    "notion_create_page": {"expected_seconds": 10, "background_eligible": False},
    "notion_update_page": {"expected_seconds": 10, "background_eligible": False},
}

# ── Constants ──────────────────────────────────────────────

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


# ── Client ─────────────────────────────────────────────────


class NotionClient:
    """Thin wrapper around the Notion API."""

    def __init__(self) -> None:
        self.token = get_credential(
            "notion", "notion", key_name="api_key", env_var="NOTION_API_KEY",
        )
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    def _post(self, path: str, body: dict) -> dict:
        r = httpx.post(
            f"{NOTION_API_BASE}{path}",
            headers=self.headers,
            json=body,
            timeout=30.0,
        )
        r.raise_for_status()
        return r.json()

    def _patch(self, path: str, body: dict) -> dict:
        r = httpx.patch(
            f"{NOTION_API_BASE}{path}",
            headers=self.headers,
            json=body,
            timeout=30.0,
        )
        r.raise_for_status()
        return r.json()

    # ── Query Database ────────────────────────────────────

    def query_database(
        self,
        database_id: str,
        filter: dict | None = None,
        page_size: int = 100,
    ) -> list[dict]:
        """Query a Notion database and return simplified results."""
        body: dict[str, Any] = {"page_size": min(page_size, 100)}
        if filter:
            body["filter"] = filter

        data = self._post(f"/databases/{database_id}/query", body)
        results = []
        for page in data.get("results", []):
            props = page.get("properties", {})
            simplified = {"page_id": page["id"]}
            for key, val in props.items():
                simplified[key] = self._extract_property_value(val)
            results.append(simplified)
        return results

    # ── Create Page ───────────────────────────────────────

    # DB別の必須フィールド（dashes除去済みUUID→必須プロパティ名リスト）
    # クラウドワークス案件管理DBには おすすめ度 を必ず登録すること
    _DB_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
        "2e31158c25dc814a9f1af021f2b7007d": ("案件名", "案件URL", "おすすめ度"),
    }

    def create_page(
        self,
        database_id: str,
        properties: dict[str, Any],
    ) -> dict:
        """Create a page in a Notion database."""
        # DB別必須フィールド検証
        db_key = database_id.replace("-", "")
        required = self._DB_REQUIRED_FIELDS.get(db_key)
        if required:
            # 接頭辞 "text:" などを除いた実際のキー名で判定
            actual_keys = {k.split(":", 1)[-1] if ":" in k else k for k in properties}
            missing = [k for k in required if k not in actual_keys]
            if missing:
                raise ValueError(
                    f"Notion create_page: DB {database_id} は次のフィールドが必須です: "
                    f"{missing}. 提供されたキー: {sorted(actual_keys)}"
                )
        body = {
            "parent": {"database_id": database_id},
            "properties": self._build_properties(properties),
        }
        result = self._post("/pages", body)
        return {"page_id": result["id"], "url": result.get("url", "")}

    # ── Update Page ───────────────────────────────────────

    def update_page(
        self,
        page_id: str,
        properties: dict[str, Any],
    ) -> dict:
        """Update properties of an existing Notion page."""
        body = {"properties": self._build_properties(properties)}
        result = self._patch(f"/pages/{page_id}", body)
        return {"page_id": result["id"], "url": result.get("url", "")}

    # ── Property Helpers ──────────────────────────────────

    @staticmethod
    def _extract_property_value(prop: dict) -> Any:
        """Extract a simple Python value from a Notion property object."""
        t = prop.get("type", "")
        if t == "title":
            parts = prop.get("title", [])
            return "".join(p.get("plain_text", "") for p in parts)
        if t == "rich_text":
            parts = prop.get("rich_text", [])
            return "".join(p.get("plain_text", "") for p in parts)
        if t == "number":
            return prop.get("number")
        if t == "select":
            sel = prop.get("select")
            return sel.get("name") if sel else None
        if t == "multi_select":
            return [s.get("name") for s in prop.get("multi_select", [])]
        if t == "date":
            d = prop.get("date")
            return d.get("start") if d else None
        if t == "checkbox":
            return prop.get("checkbox", False)
        if t == "url":
            return prop.get("url")
        if t == "email":
            return prop.get("email")
        if t == "phone_number":
            return prop.get("phone_number")
        if t == "status":
            s = prop.get("status")
            return s.get("name") if s else None
        return None

    @staticmethod
    def _build_properties(props: dict[str, Any]) -> dict:
        """Build Notion API property objects from simple key-value pairs.

        Supports a type hint prefix: "title:", "text:", "number:", "select:",
        "date:", "checkbox:", "url:".
        If no prefix, auto-detects based on value type.
        """
        result = {}
        for key, value in props.items():
            # Check for explicit type prefix
            if ":" in key and key.split(":")[0] in (
                "title", "text", "number", "select", "date", "checkbox", "url",
            ):
                type_hint, real_key = key.split(":", 1)
            else:
                type_hint = None
                real_key = key

            # Skip None / empty values for types where empty is invalid
            # (date/url/select cannot accept empty string — causes 400)
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                # empty string: skip for date/url/select/number; allow for text/title
                if type_hint in ("date", "url", "select", "number"):
                    continue
                if type_hint is None and (
                    real_key.endswith("日") or real_key.endswith("期限")
                    or real_key.endswith("URL")
                    or real_key in ("ステータス", "報酬形態", "カテゴリ")
                ):
                    continue

            if type_hint == "title" or (type_hint is None and real_key in ("案件名", "Name", "title")):
                result[real_key] = {
                    "title": [{"text": {"content": str(value)}}],
                }
            elif type_hint == "text":
                result[real_key] = {
                    "rich_text": [{"text": {"content": str(value)}}],
                }
            elif type_hint == "number" or (type_hint is None and isinstance(value, (int, float))):
                result[real_key] = {"number": value}
            elif type_hint == "select" or (
                type_hint is None and isinstance(value, str) and real_key in (
                    "ステータス", "報酬形態", "カテゴリ",
                )
            ):
                result[real_key] = {"select": {"name": str(value)}}
            elif type_hint == "date" or (
                type_hint is None and isinstance(value, str) and (
                    real_key.endswith("日") or real_key.endswith("期限")
                )
            ):
                result[real_key] = {"date": {"start": value}}
            elif type_hint == "checkbox" or (type_hint is None and isinstance(value, bool)):
                result[real_key] = {"checkbox": value}
            elif type_hint == "url" or (
                type_hint is None and isinstance(value, str) and real_key.endswith("URL")
            ):
                result[real_key] = {"url": value}
            else:
                # Default to rich_text
                result[real_key] = {
                    "rich_text": [{"text": {"content": str(value)}}],
                }

        return result


# ── Tool Schemas ───────────────────────────────────────────


def get_tool_schemas() -> list[dict]:
    """Return Anthropic tool_use schemas."""
    return [
        {
            "name": "notion_query_database",
            "description": (
                "Notion データベースを検索する。フィルタ条件を指定して"
                "ページ一覧を取得する。"
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "database_id": {
                        "type": "string",
                        "description": "Notion データベースID",
                    },
                    "filter": {
                        "type": "object",
                        "description": "Notion API フィルタオブジェクト（省略可）",
                    },
                    "page_size": {
                        "type": "integer",
                        "description": "取得件数（最大100、デフォルト100）",
                        "default": 100,
                    },
                },
                "required": ["database_id"],
            },
        },
        {
            "name": "notion_create_page",
            "description": (
                "Notion データベースに新しいページ（行）を作成する。"
                "プロパティをキー: 値の辞書で指定する。"
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "database_id": {
                        "type": "string",
                        "description": "Notion データベースID",
                    },
                    "properties": {
                        "type": "object",
                        "description": (
                            "プロパティ辞書。キーはプロパティ名、値は設定する値。"
                            "型はプロパティ名から自動判定。明示したい場合は "
                            "'type:プロパティ名' 形式で指定可（例: 'text:メモ'）"
                        ),
                    },
                },
                "required": ["database_id", "properties"],
            },
        },
        {
            "name": "notion_update_page",
            "description": (
                "Notion ページのプロパティを更新する。"
                "更新したいプロパティのみ指定する。"
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "page_id": {
                        "type": "string",
                        "description": "Notion ページID",
                    },
                    "properties": {
                        "type": "object",
                        "description": "更新するプロパティ辞書",
                    },
                },
                "required": ["page_id", "properties"],
            },
        },
    ]


# ── Dispatch ──────────────────────────────────────────


def dispatch(name: str, args: dict[str, Any]) -> Any:
    """Dispatch a tool call by schema name."""
    args.pop("anima_dir", None)
    client = NotionClient()

    if name == "notion_query_database":
        return client.query_database(
            database_id=args["database_id"],
            filter=args.get("filter"),
            page_size=args.get("page_size", 100),
        )
    if name == "notion_create_page":
        return client.create_page(
            database_id=args["database_id"],
            properties=args["properties"],
        )
    if name == "notion_update_page":
        return client.update_page(
            page_id=args["page_id"],
            properties=args["properties"],
        )
    raise ValueError(f"Unknown tool: {name}")


# ── CLI ────────────────────────────────────────────────


def cli_main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Notion API tool")
    sub = parser.add_subparsers(dest="command")

    q = sub.add_parser("query", help="Query a database")
    q.add_argument("database_id")
    q.add_argument("--page-size", type=int, default=10)

    c = sub.add_parser("create", help="Create a page")
    c.add_argument("database_id")
    c.add_argument("--props", type=str, required=True, help="JSON properties")

    u = sub.add_parser("update", help="Update a page")
    u.add_argument("page_id")
    u.add_argument("--props", type=str, required=True, help="JSON properties")

    args = parser.parse_args(argv)

    if args.command == "query":
        client = NotionClient()
        results = client.query_database(args.database_id, page_size=args.page_size)
        print(json.dumps(results, ensure_ascii=False, indent=2))
    elif args.command == "create":
        client = NotionClient()
        props = json.loads(args.props)
        result = client.create_page(args.database_id, props)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "update":
        client = NotionClient()
        props = json.loads(args.props)
        result = client.update_page(args.page_id, props)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        parser.print_help()
