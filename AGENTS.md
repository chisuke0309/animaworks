# AGENTS.md — animaworks

## プロジェクト概要

**AnimaWorks** — Organization-as-Code for autonomous AI agents.
エージェントを「ツール」ではなく「自律的な人」として動かすフレームワーク。
各エージェント（Anima）は固有の名前・性格・記憶・スケジュールを持ち、チームとして協働する。

- **GitHub (upstream)**: https://github.com/xuiltul/animaworks
- **License**: Apache License 2.0 / Public OSS

---

## システムファイル索引

AnimaWorksを構成する重要ファイルの一覧。**新しいセッションではまずここを参照すること。**

### 組織・設定（ソース・オブ・トゥルース）

| ファイル | 役割 | 備考 |
|---------|------|------|
| `~/.animaworks/config.json` | AnimaのDB（unit / model / supervisor / heartbeat等の構造化データ） | 機械的参照はここ |
| `~/.animaworks/common_knowledge/organization/goals.md` | 組織目標・事業部定義・メンバー構成・KPI | LLMが読む文脈はここ |

### Anima個別ファイル（per anima: `~/.animaworks/animas/<name>/`）

| ファイル | 役割 |
|---------|------|
| `identity.md` | 人格・名前・性格・口調・所属事業部 |
| `injection.md` | 行動指針・専門領域・委任ルール・禁止事項 |
| `cron.md` | スケジュール定義（`schedule: M H * * *` 形式） |
| `permissions.md` | 使用可能ツール一覧 |
| `status.json` | 有効/無効フラグ、モード設定 |
| `knowledge/*.md` | 学習知識・戦略・ルール・ログ |
| `state/task_queue.jsonl` | タスクキュー（pending/in_progress/completed） |
| `state/conversation.json` | 直近の会話履歴（HBのsystem_promptに注入） |
| `activity_log/YYYY-MM-DD.jsonl` | 行動ログ（詳細） |
| `episodes/YYYY-MM-DD.md` | 日次サマリー（search_memoryの主要ソース） |
| `vectordb/` | ChromaDB ベクトルDB（episodes/knowledgeのembedding） |

### スクリプト・ツール（本リポジトリ）

| ファイル | 役割 |
|---------|------|
| `scripts/knowledge_lint.py` | 知識整合性チェッカー（ハンドオフ時に自動実行） |
| `core/_anima_heartbeat.py` | Heartbeat実行パス |
| `core/_anima_inbox.py` | Inbox実行パス |
| `core/_anima_lifecycle.py` | Cron実行パス |
| `core/tools/tiktok_analytics.py` | TikTokエンゲージメント収集・分析 |

### 運用ドキュメント（本リポジトリ）

| ファイル | 役割 |
|---------|------|
| `AGENTS.md`（本ファイル） | プロジェクトルール・仕様・チェックリスト |
| `.agent/handoff/HANDOFF.md` | 直近セッションの引き継ぎ |
| `.claude/commands/handoff.md` | `/handoff` コマンドの仕様 |
| `.agent/skills/` | Claude Code向け運用スキル |

---

## Git リポジトリ構成

| remote | URL | 用途 |
|--------|-----|------|
| `origin` | `https://github.com/xuiltul/animaworks.git` | upstream（pull のみ） |
| `fork` | `https://github.com/chisuke0309/animaworks.git` | 自分の fork（push 先） |

- **push は必ず `fork` remote へ**。`origin` には push しない
- upstream の最新取り込み: `git fetch origin && git merge origin/main`

---

## プロジェクト構成

```
animaworks/
├── main.py              # CLI エントリポイント
├── core/                # コアエンジン
│   ├── anima.py         #   カプセル化された人格クラス
│   ├── agent.py         #   実行モード選択・サイクル管理
│   ├── anima_factory.py #   Anima 生成
│   ├── memory/          #   記憶サブシステム
│   │   ├── manager.py   #     書庫型記憶の検索・書き込み
│   │   ├── priming.py   #     自動想起レイヤー（4チャネル並列）
│   │   ├── consolidation.py # 記憶統合（日次/週次）
│   │   ├── forgetting.py #   能動的忘却（3段階）
│   │   └── rag/         #     RAG エンジン（ChromaDB + embeddings）
│   ├── execution/       #   実行エンジン（A1/A1F/A2/B）
│   ├── tooling/         #   ツールディスパッチ・権限チェック
│   ├── prompt/          #   システムプロンプト構築（24 セクション）
│   ├── supervisor/      #   プロセス隔離（Unix ソケット）
│   └── tools/           #   外部ツール実装
├── cli/                 # CLI パッケージ（argparse + サブコマンド）
├── server/              # FastAPI サーバー + Web UI
│   ├── routes/          #   API ルート（ドメイン別）
│   └── static/          #   ダッシュボード + Workspace UI
└── templates/           # デフォルト設定・プロンプトテンプレート
    ├── roles/            #   ロールテンプレート（6 種）
    └── anima_templates/  #   Anima スケルトン
```

---

## 実行モード（重要）

コードを読む上で必ず把握しておくこと。

| モード | エンジン | 対象モデル | ツール |
|--------|----------|-----------|--------|
| **A1** | Claude Agent SDK | Claude（推奨） | フル: Read/Write/Edit/Bash/Grep/Glob |
| **A1 Fallback** | Anthropic SDK 直接 | Claude（Agent SDK 未インストール時） | search_memory, read/write_file 等 |
| **A2** | LiteLLM + tool_use | GPT-4o, Gemini 等 | search_memory, read/write_file 等 |
| **B** | LiteLLM テキストベース | Ollama, ローカルモデル | 疑似ツールコール（テキスト解析） |

モードはモデル名から自動判定。`config.json` で個別オーバーライド可能。

---

## 記憶システム（アーキテクチャ）

| ディレクトリ | 脳科学モデル | 内容 |
|---|---|---|
| `episodes/` | エピソード記憶 | 日別の行動ログ |
| `knowledge/` | 意味記憶 | 教訓・ルール・学んだ知識 |
| `procedures/` | 手続き記憶 | 作業手順書 |
| `state/` | ワーキングメモリ | 今のタスク・未完了項目 |
| `shortterm/` | 短期記憶 | セッション継続 |
| `activity_log/` | 統一タイムライン | 全インタラクション（JSONL） |

---

## 技術スタック

| コンポーネント | 技術 |
|---|---|
| エージェント実行 | Claude Agent SDK / Anthropic SDK / LiteLLM |
| Web フレームワーク | FastAPI + Uvicorn |
| タスクスケジュール | APScheduler |
| 設定管理 | Pydantic + JSON + Markdown |
| 記憶基盤 | ChromaDB + sentence-transformers |
| グラフ活性化 | NetworkX（拡散活性化 + PageRank） |
| パッケージ管理 | uv |

---

## タスクキュー保守契約（厳守）

Animaのタスクキュー（`state/task_queue.jsonl`）は、**全ての実行パス**で保守処理を実行しなければならない。
新しい実行パスを追加する場合、この契約を必ず遵守すること。

### 3つの保守関数

| 関数 | 役割 | 閾値 |
|------|------|------|
| `auto_block_stale_tasks()` | 2時間以上更新のないpending/in_progressをblocked化 | 2h |
| `auto_resolve_old_tasks()` | 24時間以上更新のない全非終端タスクをdone化 | 24h |
| `maybe_compact()` | JONLファイルのGC（終了済みタスクの削除・圧縮） | 行数閾値 |

### 実行パスと呼び出し箇所

**3関数は必ずセットで呼ぶこと。** `auto_block` だけ呼んで `auto_resolve` / `maybe_compact` を呼ばないのはバグである。

| 実行パス | 対象Anima | 呼び出し箇所 | タイミング |
|---------|-----------|-------------|-----------|
| **Heartbeat** | `active_hours` 指定あり | `core/_anima_heartbeat.py` `_handle_stale_task_auto_blocking()` | LLM実行前 |
| **Inbox** | `inbox_only` モード | `core/_anima_inbox.py` inbox処理ブロック内 | LLM実行前 |
| **Cron** | 全Anima（モード問わず） | `core/_anima_lifecycle.py` `run_cron_task()` | LLM実行前 |

### Animaモードと実行パスの対応

| モード | Heartbeat | Inbox | Cron |
|--------|-----------|-------|------|
| `active_hours: HH-HH` | 定期実行 | メッセージ受信時 | スケジュール通り |
| `active_hours: inbox_only` | **実行されない** | メッセージ受信時 | スケジュール通り |
| `active_hours: off` | **実行されない** | **実行されない** | スケジュール通り |

> **注意**: `inbox_only` / `off` モードではHeartbeatが動かないため、Inbox/Cronパスでの保守が唯一の安全弁となる。
> 新しい実行パス（例: API経由の手動トリガー等）を追加する際も、LLM実行前に3関数を必ず呼ぶこと。

---

## 開発コマンド

```bash
# サーバー起動（フォアグラウンド）
uv run python main.py serve --foreground   # http://localhost:18500

# サーバー起動（バックグラウンド）
uv run python main.py start

# テスト
uv run pytest tests/ -v

# CLI ヘルプ
uv run python main.py --help
```

---

## Anima追加・変更時の必須チェックリスト

新しいAnimaを追加、または既存Animaのモデル・ロールを変更する際は、以下を**全て**更新すること。
漏れがあると lint エラー・ハンドオフ不整合・org_alignment チェック失敗の原因になる。

### Anima新規追加時

| # | 対象ファイル | 更新内容 |
|---|------------|---------|
| 1 | `~/.animaworks/animas/<name>/` | identity / injection / cron / permissions / status.json の5ファイル作成 |
| 2 | `~/.animaworks/config.json` | `animas` セクションにエントリ追加（`unit` / `supervisor` / `heartbeat_offset_minutes` 等） |
| 3 | `~/.animaworks/common_knowledge/organization/goals.md` | 所属事業部のメンバーテーブルに行を追加。新事業部の場合は unit セクション（`<!-- unit:xxx -->`）ごと追加 |
| 4 | `.claude/commands/handoff.md` | モデル構成テーブルに行を追加 |

### モデル・ロール変更時

| # | 対象ファイル | 更新内容 |
|---|------------|---------|
| 1 | `~/.animaworks/config.json` | `anima_defaults.model` またはAnima個別の `model` を変更 |
| 2 | `.claude/commands/handoff.md` | モデル構成テーブルのモデル名を更新 |

### 変更後の確認

```bash
# 1. lint が通ること（critical 0）
python3 scripts/knowledge_lint.py

# 2. cron パースが正しいこと
python3 -c "
from core.schedule_parser import parse_cron_md
import os
name = '<anima名>'
cron_md = open(os.path.expanduser(f'~/.animaworks/animas/{name}/cron.md')).read()
tasks = parse_cron_md(cron_md)
print(f'{name}: {len(tasks)} tasks')
for t in tasks: print(f'  {t.name} | schedule={t.schedule}')
"

# 3. サーバー再起動
launchctl kickstart -k gui/$(id -u)/com.animaworks.server
```

---

## スキル運用ルール（AnimaWorks固有）

### プロジェクト固有スキル

AnimaWorks固有の運用スキル（Claude Code / 人間向け）は `.agent/skills/` に配置する。
**作業を始める前に `.agent/skills/animaworks-skills-index/` で関連スキルを確認すること。**

### Anima用スキル（common_skills）

全Animaが共有するスキルは `~/.animaworks/common_skills/` に配置する（テンプレート元: `templates/ja/common_skills/`）。
**Anima個別の `skills/` ディレクトリにコピー配布しない。** 同じスキルの複数コピーは更新漏れの原因になる。
