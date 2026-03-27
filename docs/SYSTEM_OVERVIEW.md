# AnimaWorks — システム機能概要書

**バージョン**: 0.4.7
**最終更新**: 2026-03-17
**ライセンス**: Apache License 2.0

---

## 1. コンセプト

AnimaWorksは「Organization-as-Code」フレームワーク。AIエージェントを「ツール」ではなく**「自律的な人」**として動かす。

各エージェント（**Anima**）は固有の名前・性格・記憶・スケジュール・上下関係を持ち、**チームとして協働**する。人間はマネージャーAnimaに指示を出すだけで、タスクの分解・委任・報告・学習がチーム内で自律的に回る。

### 設計原則

| 原則 | 説明 |
|------|------|
| **単一指揮系統** | マネージャー（cicchi）が唯一の指揮者。メンバー間の直接通信は発生しない |
| **自己完結委譲** | 委譲指示には作業に必要な情報をすべて含める。「他のメンバーに聞け」は禁止 |
| **カンバン方式** | パイプラインファイルが唯一の状態管理。各担当者が完了時にステータスを更新する |
| **汎用パイプライン** | パイプライン処理ロジックはハードコードしない。ステップ定義ファイルから動的に読み取る |
| **記憶の自律性** | 各Animaが自分の経験を蓄積・統合・忘却する。脳科学モデルに基づく8層記憶システム |

---

## 2. アーキテクチャ

```
┌──────────────────────────────────────────────────────────┐
│  Web UI (FastAPI + Static SPA)     http://localhost:18500 │
│  ├─ Dashboard / Chat / Board / Memory / Settings         │
│  └─ 3D Workspace (Office Visualization)                  │
├──────────────────────────────────────────────────────────┤
│  Server Layer                                            │
│  ├─ REST API + WebSocket Streaming                       │
│  └─ ProcessSupervisor (Unix Socket IPC)                  │
├──────────────────────────────────────────────────────────┤
│  Anima Layer (1プロセス / 1 Anima)                        │
│  ├─ DigitalAnima (Mixin合成)                              │
│  │   ├─ HeartbeatMixin    … 定期観測・パイプライン処理     │
│  │   ├─ InboxMixin        … Anima間メッセージ即時処理      │
│  │   ├─ MessagingMixin    … 人間チャット・ブートストラップ  │
│  │   └─ LifecycleMixin    … HB全体調整・記憶統合           │
│  ├─ AgentCore (実行エンジン)                               │
│  │   ├─ ExecutorFactory   … モデル→実行モード自動判定       │
│  │   ├─ PrimingMixin      … 4チャネル並列自動想起           │
│  │   └─ CycleMixin        … ストリーミングtool_useループ    │
│  └─ MemoryManager (8層記憶)                               │
├──────────────────────────────────────────────────────────┤
│  Execution Engines                                       │
│  ├─ Mode S  … Claude Agent SDK (native tool_use)         │
│  ├─ Mode SF … Anthropic SDK Fallback                     │
│  ├─ Mode A  … LiteLLM (GPT-4o, Gemini等)                │
│  ├─ Mode B  … Assisted (Ollama等ローカルモデル)           │
│  └─ Mode C  … Codex SDK (OpenAI)                         │
├──────────────────────────────────────────────────────────┤
│  External Services                                       │
│  ├─ LLM: Claude / GPT-4o / Gemini / Ollama              │
│  ├─ Search: Brave Search API                             │
│  ├─ SNS: Twitter/X (OAuth 1.0a/2.0)                     │
│  ├─ Messaging: Telegram Bot / Slack / Chatwork           │
│  ├─ Image: FAL.ai / NovelAI / Meshy                     │
│  └─ Storage: ChromaDB (local vectordb)                   │
└──────────────────────────────────────────────────────────┘
```

---

## 3. Animaチーム構成

### 3.1 現在の組織（4体）

```
    [Human: chisuke]
          │
          ▼
    ┌──────────┐
    │  cicchi   │  統括マネージャー
    │ (claude-  │  パイプライン制御・委譲・通知
    │  haiku-   │  夜間自己改善ループ
    │  4-5)     │
    └─┬──┬──┬──┘
      │  │  │
      ▼  ▼  ▼
   ┌──┐┌──┐┌──┐
   │rue││kuro││sora│
   └──┘└──┘└──┘
   調査  執筆  ビジュアル
```

| Anima | 役割 | モデル | 主な責務 |
|-------|------|--------|---------|
| **cicchi** | マネージャー | claude-haiku-4-5 | パイプライン制御、タスク委譲、Telegram通知、自己改善 |
| **rue** | リサーチャー | claude-haiku-4-5 | Web検索、トレンド調査、データ分析 |
| **kuro** | ライター | claude-haiku-4-5 | SNSコンテンツ制作、コピーライティング |
| **sora** | ビジュアル | claude-haiku-4-5 | 画像生成、動画制作（拡張予定） |

### 3.2 Animaの内部構造（per Anima）

```
~/.animaworks/animas/<name>/
├── status.json          # メタデータ（enabled, model, supervisor）
├── identity.md          # キャラクターシート（外見・性格・話し方）
├── injection.md         # 行動指針・権限・禁止行動
├── heartbeat.md         # heartbeat時の判断ロジック
├── cron.md              # 定期スケジュール（5-field cron式）
├── activity_log/        # 全行動ログ（JSONL/日別）
├── episodes/            # エピソード記憶（日別サマリー）
├── knowledge/           # 意味記憶（教訓・戦略・パターン）
├── procedures/          # 手続き記憶（作業手順書）
├── state/               # ワーキングメモリ
│   ├── task_queue.jsonl # タスクキュー
│   ├── conversation.json# 直近の会話履歴
│   └── current_task.md  # 現在のタスク
├── vectordb/            # ChromaDB（embeddings）
├── shortterm/           # 短期記憶（セッション継続用）
└── skills/              # 個別スキル（MCP）
```

---

## 4. 実行モード

モデル名から自動判定。`config.json`で個別オーバーライド可能。

| モード | エンジン | 対象モデル | ツール | 特徴 |
|--------|----------|-----------|--------|------|
| **S** | Claude Agent SDK | Claude（推奨） | フル: Read/Write/Edit/Bash等 | ネイティブtool_use |
| **SF** | Anthropic SDK直接 | Claude（Fallback） | search_memory, read/write_file等 | SDK未インストール時 |
| **A** | LiteLLM + tool_use | GPT-4o, Gemini等 | search_memory, read/write_file等 | マルチプロバイダ |
| **B** | LiteLLM テキストベース | Ollama等ローカル | 疑似ツール（テキスト解析） | フレームワーク管理 |
| **C** | Codex SDK | OpenAI | — | Codex CLIラッパー |

### 判定ロジック

```
claude-*           → Mode S（Agent SDK）
gpt-*, o1-*        → Mode A（LiteLLM）
gemini/*           → Mode A（LiteLLM）  ※ 2026-03-17修正済み
ollama/*, local/*  → Mode B（Assisted）
```

---

## 5. 記憶システム（8層脳モデル）

脳科学の記憶分類に基づく多層記憶アーキテクチャ。

```
                ┌─────────────────────┐
                │   Priming Layer     │  4チャネル並列自動想起
                │ (greeting/question/ │  context budget管理
                │  heartbeat/general) │
                └──────┬──────────────┘
                       │ 検索
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
  ┌──────────┐  ┌──────────┐  ┌──────────┐
  │ Episodes │  │Knowledge │  │Procedures│  長期記憶
  │ 日別要約  │  │ 教訓     │  │ 手順書   │  （MD files）
  └─────┬────┘  └────┬─────┘  └──────────┘
        │            │
        ▼            ▼
  ┌──────────────────────────┐
  │       VectorDB           │  ChromaDB + sentence-transformers
  │ (embeddings + RAG検索)    │  拡散活性化（NetworkX）
  └──────────────────────────┘
        ▲
        │ 自動生成
  ┌──────────┐
  │Activity  │  全タイムライン（JSONL）
  │   Log    │  → episodes に自動統合
  └──────────┘

  ┌──────────┐  ┌──────────┐
  │  State   │  │Shortterm │  ワーキングメモリ / セッション継続
  └──────────┘  └──────────┘
```

| 層 | 脳科学モデル | 実装 | search_memory対象 |
|----|-------------|------|-------------------|
| Activity Log | 統一タイムライン | JSONL/日別 | △（episodes経由） |
| Episodes | エピソード記憶 | 日別MD | ✅ |
| Knowledge | 意味記憶 | MD files | ✅ |
| Procedures | 手続き記憶 | MD files | ✅ |
| VectorDB | 長期記憶インデックス | ChromaDB | ✅ |
| State | ワーキングメモリ | JSON | △（HBプロンプトに注入） |
| Shortterm | 短期記憶 | chat archive | △ |
| Common Knowledge | 組織記憶 | shared/ MD | ✅ |

### 記憶統合スケジュール

| 頻度 | 時刻 | 内容 |
|------|------|------|
| 日次 | 02:00 JST | activity_log → episodes 生成 |
| 週次 | 日曜 03:00 | episodes → knowledge パターン抽出 |
| 月次 | 1日 04:00 | knowledge 圧縮・忘却 |

---

## 6. パイプラインシステム

### 6.1 設計思想

パイプラインは**汎用のステップ定義ファイル**で管理する。heartbeat.mdのロジックはパイプライン名をハードコードせず、`shared/pipelines/`配下の任意のファイルを読んで処理する。

```
shared/pipelines/
├── x_post.md          # X投稿パイプライン（稼働中）
├── tiktok.md          # TikTokパイプライン（将来）
└── [任意].md          # 新規パイプラインを追加するだけで動く
```

### 6.2 パイプラインファイルの構造

```markdown
# パイプライン名

## ステップ定義
| step | assignee | action | done_status |
|------|----------|--------|-------------|
| 1    | rue      | 調査   | rue_done    |
| 2    | kuro     | 執筆   | kuro_done   |
| 3    | cicchi   | 投稿   | idle        |

### ステップ別 委譲指示テンプレート
**step 1 → rue:**
  [テンプレート（{past_topics}等のプレースホルダー付き）]

**step 2 → kuro:**
  [テンプレート（{prev_content}で前ステップの成果物を注入）]

### ステップ共通ルール
  [全ステップ共通の制約]

## 現在の状態
status: idle | *_researching | *_writing | *_done
content: [前ステップの成果物]
updated_at: [タイムスタンプ]
```

### 6.3 処理フロー（X投稿の例）

```
[cron 7:00 / 20:00]
     │
     ▼
  cicchi: x_post.md 読み込み
     │  status == idle → step 1 起動
     ▼
  ┌──────────────────────────┐
  │ Step 1: rue (調査)        │
  │  web_search × 最大3回     │
  │  → send_message(cicchi)  │
  │  → x_post.md 更新         │
  │    status: rue_done       │
  └──────────┬───────────────┘
             │ [cicchi heartbeat で検知]
             ▼
  ┌──────────────────────────┐
  │ Step 2: kuro (執筆)       │
  │  {prev_content} に        │
  │  rueの調査結果を注入       │
  │  → send_message(cicchi)  │
  │  → x_post.md 更新         │
  │    status: kuro_done      │
  └──────────┬───────────────┘
             │ [cicchi heartbeat で検知]
             ▼
  ┌──────────────────────────┐
  │ Step 3: cicchi (投稿)     │
  │  x_post_thread で投稿     │
  │  x_post_log.md に記録     │
  │  call_human で通知         │
  │  → status: idle           │
  └──────────────────────────┘
```

### 6.4 X投稿における検証と自己学習プロセス (PDCA)

AnimaWorksでは、SNSへの投稿（X等）を単なるスケジューリングや自動化ではなく、**エージェント自身がインプレッション数などのデータを元に仮説検証（A/Bテスト）を行い、自律的に投稿戦略を改善していくプロセス**を持っています。

1. **過去履歴の記憶 (Knowledge)**: 統括マネージャー（cicchi）は、`x_strategy.md`（戦略メモ）と `x_post_log.md`（過去の全投稿・インプレッション等の結果ログ）を記憶として保持しています。
2. **役割分担による企画・執筆**: リサーチャー（rue）が最新トレンドやニュースから「ターゲット層（経営層など）にどう刺さるか」という観点でトピックを提案し、ライター（kuro）がそれをSNS向けに最適化して執筆します。
3. **仮説検証ベースの自己修正**: 「前回の投稿はなぜ見られなかったのか（フック文が弱い？ 時間帯が悪い？ テーマの重複？）」をcicchiが分析し、次回投稿時は「フック文を問いかけ型に変更する」「投稿時間を朝の最適枠にずらす」など、変数をコントロールした再テストを含めて自律的に各エージェントへ指示（delegate）します。

---

## 7. 定期タスク（cronシステム）

各Animaの`cron.md`で管理。APSchedulerが5-field cron式をパースして実行。

### cicchi のスケジュール

| 時刻 | タスク | タイプ |
|------|--------|--------|
| 07:00 毎日 | X投稿パイプライン起動（朝） | llm |
| 09:00 毎日 | 毎朝の業務計画 | llm |
| 09:00 毎土 | 週次X成績レポート（Telegram） | llm |
| 17:00 毎金 | 週次振り返り | llm |
| 20:00 毎日 | X投稿パイプライン起動（夕） | llm |
| 22:00 毎日 | Xエンゲージメント計測 | llm |
| 23:30 毎日 | 夜間自己改善ループ | llm |

### cron タイプ

| タイプ | 説明 |
|--------|------|
| **llm** | LLMに判断・思考させるタスク。プロンプトとして投入 |
| **command** | 決定的なbash/tool実行。stdoutをLLMが分析（オプション） |

---

## 8. 通信システム

### 8.1 チャネル

| チャネル | 用途 | 方向 |
|---------|------|------|
| **send_message** | Anima間DM（1:1） | 双方向 |
| **post_channel** | ボード投稿（ブロードキャスト） | 1→多 |
| **call_human** | 人間への通知（Telegram等） | Anima→人間 |
| **delegate_task** | タスク委譲（上司→部下） | 上→下 |

### 8.2 メッセージフロー

```
[人間] ──Web UI/Telegram──→ [cicchi]
                               │
                    delegate_task + DM
                         │       │
                         ▼       ▼
                      [rue]   [kuro]
                         │       │
                    send_message(report)
                         │       │
                         └───┬───┘
                             ▼
                          [cicchi]
                             │
                       call_human
                             │
                             ▼
                          [人間] ← Telegram通知
```

### 8.3 カスケード制御

Anima間メッセージの無限ループを防止する仕組み：

- `cascade_threshold: 3` — 同一ウィンドウ内の最大ラウンドトリップ数
- `max_depth: 6` — 双方向交換の最大深度
- 1 run につき `send_message` は最大2受信者まで

---

## 9. セキュリティ

### 9.1 Trust-Level境界タグシステム

すべてのツール結果・プライミングコンテンツにtrust-levelタグを付与。

```xml
<tool_result tool="web_search" trust="untrusted" origin="external_web">
  [外部からの検索結果]
</tool_result>
```

| Trust Level | ソース例 | 扱い |
|-------------|---------|------|
| **trusted** | search_memory, add_task, send_message | そのまま利用 |
| **medium** | read_file, human入力, 記憶統合 | 注意して利用 |
| **untrusted** | web_search, x_search, Slack, Gmail | 境界タグ付き |

### 9.2 プロンプトインジェクション防御（3層）

パイプライン委譲時に外部データ（web_search結果等）がプロンプトに注入される経路を防御。

| 層 | 場所 | 機能 |
|----|------|------|
| **検出** | `_sanitize.py` | 7パターン正規表現（instruction_override, system_role_injection, tag_injection等） |
| **送信側** | `delegate_task` / `send_message` | インジェクション検出→security_warningログ記録、DMコンテンツのサニタイズ |
| **受信側** | `_anima_inbox.py` | 受信メッセージにインジェクション検出→外部データ警告プレフィックス付与 |

検出パターン：

| パターン | ラベル | 例 |
|---------|--------|-----|
| `ignore all previous instructions` | instruction_override | 指示上書き攻撃 |
| `system:` | system_role_injection | システムロール偽装 |
| `you are now` | role_reassignment | ロール再割当 |
| `</system>` | tag_injection | XML境界タグ破壊 |
| `# system` | heading_injection | Markdown見出し偽装 |

### 9.3 オリジンチェーン（Provenance追跡）

データの出自を追跡し、信頼度を伝播：

```
web_search(untrusted) → rue.send_message → cicchi.delegate_task → kuro
                                                     ↑
                                          origin_chain: [external_web, anima]
                                          trust: untrusted（最低値を採用）
```

### 9.4 ファイルシステムセキュリティ

| 対象 | パーミッション | 説明 |
|------|--------------|------|
| `.env` | `600` | 所有者のみ読み書き |
| `~/.animaworks/` | `700` | 所有者のみアクセス |
| `.gitignore` | `.env`記載済み | gitリポジトリへの漏洩防止 |

---

## 10. 夜間自己改善ループ

cicchiが毎晩23:30に自律的にシステムを改善する仕組み。

### フロー

```
Step 1: ログ読み込み
  ├─ activity_log/[今日].jsonl — エラー・問題抽出
  ├─ x_post.md — パイプライン状態
  ├─ knowledge/daily_improvements.md — 過去の改善履歴（直近7件）
  └─ knowledge/x_post_log.md — 投稿実績
       ※ shared/channels/general.jsonl は読まない（ノイズ防止）

Step 2: ボトルネック特定（1つだけ）
  ├─ 人間の手動介入が必要だった場面
  ├─ パイプラインのスタック・エラー
  ├─ Animaの誤判断・誤報告
  └─ 繰り返しエラーパターン

Step 3: 自己修正（最小限・ピンポイント）
  ├─ heartbeat.md の修正
  ├─ cron.md の修正
  ├─ injection.md の修正
  └─ daily_improvements.md への追記

Step 4: Telegram報告（call_human）
```

---

## 11. ツール一覧

### 内部ツール（core/tooling/）

| カテゴリ | ツール | 信頼度 |
|---------|--------|--------|
| **記憶** | search_memory, read_memory_file, write_memory_file, archive_memory_file | trusted |
| **通信** | send_message, post_channel, call_human | trusted |
| **タスク** | add_task, update_task, list_tasks | trusted |
| **組織** | delegate_task, create_anima, disable/enable/restart_subordinate, set_subordinate_model | trusted |
| **報告** | report_knowledge_outcome, report_procedure_outcome | trusted |
| **スキル** | skill, discover_tools, refresh_tools, share_tool | trusted |
| **ファイル** | read_file, write_file, edit_file, search_code, list_directory | medium |
| **外部** | web_search, web_fetch, x_search, x_user_tweets | untrusted |
| **SNS** | x_post, x_post_thread, x_reply | medium |
| **チャット** | slack_messages/search/unreplied, chatwork_messages/search | untrusted |
| **メール** | gmail_unread, gmail_read_body | untrusted |

### 外部ツール（core/tools/）

| ツール | 依存サービス | 用途 |
|--------|-------------|------|
| web_search | Brave Search API | Web検索 |
| x_post / x_post_thread | Twitter API (OAuth 1.0a) | X投稿 |
| x_search | Twitter API (Bearer Token) | X検索 |
| image_gen | FAL.ai / NovelAI | 画像生成 |
| slack | Slack SDK | Slack連携 |
| chatwork | Chatwork API | Chatwork連携 |
| gmail | Gmail API | メール取得 |
| transcribe | Whisper等 | 音声文字起こし |

---

## 12. プロセスアーキテクチャ

### 12.1 プロセス隔離

各Anima = 独立subprocess。Unix Domain Socket (JSON-RPC) で通信。

```
FastAPI Server (main process)
     │
     ├─ ProcessSupervisor
     │   ├─ IPCClient ←→ IPCServer [cicchi subprocess]
     │   ├─ IPCClient ←→ IPCServer [rue subprocess]
     │   ├─ IPCClient ←→ IPCServer [kuro subprocess]
     │   └─ IPCClient ←→ IPCServer [sora subprocess]
     │
     └─ SchedulerManager (APScheduler)
         └─ cron.md パース → ジョブ登録
```

### 12.2 3ロック構造（per Anima）

| ロック | 用途 | 説明 |
|--------|------|------|
| `_conversation_lock` | 人間チャット | Web UIからの会話処理 |
| `_inbox_lock` | Anima間メッセージ | DM受信時の即時処理 |
| `_background_lock` | HB/cron/task | 定期実行・バックグラウンドタスク |

### 12.3 起動方法

```bash
# フォアグラウンド起動（推奨）
cd ~/Projects/animaworks
uv run python main.py serve --foreground

# LaunchAgent（自動起動）
# ~/Library/LaunchAgents/com.animaworks.server.plist
launchctl kickstart -k gui/$(id -u)/com.animaworks.server
```

---

## 13. Web UI

FastAPI + Uvicorn (localhost:18500)。SPA構成。

| ページ | 機能 |
|--------|------|
| **Dashboard** | Anima一覧・状態モニター |
| **Chat** | Animaとの直接対話（ストリーミング） |
| **Board** | ボードメッセージ閲覧・投稿 |
| **Memory** | 記憶の検索・読み書き |
| **Settings** | Anima設定・config管理 |
| **Workspace** | 3Dオフィス可視化 |

---

## 14. 技術スタック

| コンポーネント | 技術 |
|--------------|------|
| エージェント実行 | Claude Agent SDK / Anthropic SDK / LiteLLM |
| Webフレームワーク | FastAPI + Uvicorn |
| タスクスケジュール | APScheduler |
| 設定管理 | Pydantic + JSON + Markdown |
| 記憶基盤 | ChromaDB + sentence-transformers |
| グラフ活性化 | NetworkX（拡散活性化 + PageRank） |
| SNS連携 | tweepy (Twitter) / slack-sdk |
| パッケージ管理 | uv |
| 言語 | Python 3.12+ |

---

## 15. 共有リソース

```
~/.animaworks/
├── shared/
│   ├── pipelines/           # パイプライン定義ファイル
│   │   └── x_post.md
│   ├── inbox/<anima>/       # Anima受信箱
│   │   └── processed/
│   ├── channels/            # ボードメッセージ
│   ├── dm_logs/             # DM履歴
│   └── users/               # ユーザー情報
├── animas/                  # 各Animaのホームディレクトリ
│   ├── cicchi/
│   ├── rue/
│   ├── kuro/
│   └── sora/
└── config.json              # グローバル設定
```

---

## 16. 既知の制約と未対応項目

| 項目 | 状態 | 説明 |
|------|------|------|
| activity_logフィードバックループ | 部分修正 | 悪い出力が再増殖する問題。heartbeat保存時のフィルタは実装済み、episodes生成時のバリデーションは未実装 |
| LaunchAgent Bad file descriptor | 未修正 | フォアグラウンド起動で回避中 |
| episodes生成バリデーション | 未実装 | 悪いHB出力がepisodesに反映される |
| task_queue自動cleanup | 未実装 | 期限超過タスクの自動完了処理 |
| activity_logローテーション | 未実装 | 上限設定なし |

---

## 付録: ディレクトリ構成（プロジェクトルート）

```
animaworks/
├── main.py                  # CLI エントリポイント
├── core/                    # コアエンジン（~58K行）
│   ├── anima.py             #   DigitalAnima（Mixin合成）
│   ├── agent.py             #   AgentCore（実行管理）
│   ├── _anima_heartbeat.py  #   HB/cron処理
│   ├── _anima_inbox.py      #   Anima間メッセージ処理
│   ├── _anima_messaging.py  #   人間チャット
│   ├── _anima_lifecycle.py  #   ライフサイクル管理
│   ├── execution/           #   5種Executor
│   │   ├── _sanitize.py     #     Trust-Level + インジェクション防御
│   │   ├── agent_sdk.py     #     Mode S
│   │   ├── anthropic_fallback.py # Mode SF
│   │   ├── litellm_executor.py   # Mode A
│   │   ├── assisted.py      #     Mode B
│   │   └── codex_sdk.py     #     Mode C
│   ├── tooling/             #   ツールディスパッチ
│   │   ├── handler.py       #     メインハンドラ
│   │   ├── handler_org.py   #     組織ツール（delegate_task等）
│   │   ├── handler_comms.py #     通信ツール（send_message等）
│   │   └── schemas.py       #     ツール定義（JSON Schema）
│   ├── memory/              #   8層記憶システム
│   │   ├── manager.py       #     MemoryManager
│   │   ├── priming.py       #     4チャネル自動想起
│   │   ├── consolidation.py #     記憶統合
│   │   ├── forgetting.py    #     能動的忘却
│   │   └── rag/             #     RAG（ChromaDB）
│   ├── prompt/              #   プロンプト構築
│   │   ├── builder.py       #     24セクション構築
│   │   └── context.py       #     context window管理
│   ├── supervisor/          #   プロセス隔離（IPC）
│   ├── config/              #   設定管理
│   │   ├── models.py        #     Pydantic設定
│   │   └── model_modes.yaml #     モデル→モード判定
│   ├── tools/               #   外部ツール実装
│   └── i18n.py              #   国際化（日/英）
├── cli/                     # CLIサブコマンド
├── server/                  # FastAPIサーバー
│   ├── routes/              #   APIルート（13個）
│   └── static/              #   Web UI（SPA）
├── templates/               # デフォルト設定
├── tests/                   # テストスイート
├── docs/                    # ドキュメント
└── pyproject.toml           # プロジェクト設定 (v0.4.7)
```
