# AGENTS.md — animaworks

## プロジェクト概要

**AnimaWorks** — Organization-as-Code for autonomous AI agents.
エージェントを「ツール」ではなく「自律的な人」として動かすフレームワーク。
各エージェント（Anima）は固有の名前・性格・記憶・スケジュールを持ち、チームとして協働する。

- **GitHub (upstream)**: https://github.com/xuiltul/animaworks
- **License**: Apache License 2.0 / Public OSS

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
