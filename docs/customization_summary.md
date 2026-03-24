# AnimaWorks カスタマイズまとめ（本家フォーク差分）

> **ベースライン**: `87aebdd0` — Release 2026-03-01
> **現在の HEAD**: `8cd896ba` + 未コミット変更群 (2026-03-24 時点)
> **差分**: 14コミット / 59ファイル / +2,332行（コミット済み）＋ 未コミット変更あり（後述）

---

## 1. 🆕 X/Twitter 投稿機能

**新規追加**: `core/tools/x_post.py`（343行）

| 変更内容 | なぜ変更したか（ソース） |
|---------|----------------------|
| `XPostClient`・`post_tweet()`・`post_thread()` の実装、`tweepy` 依存追加 | HANDOFF (2026-03-16): 「初X投稿成功（tweet_id: 2033411796342874511）」「SNS運用代行β提供」のために実装。本家には X 連携機能が存在しない |

---

## 2. 🔒 セキュリティ強化

### 2-a. コマンドチェーン強制 / injection.md 保護 / エピソードガード
**コミット** `f37b7e96`

| 変更内容 | なぜ変更したか（コミットより） |
|---------|------------------------------|
| `injection.md` を `_PROTECTED_FILES` に追加 | Anima が `write_file`/`edit_file` で自分自身のコマンドチェーン定義を上書きできないようにするため |
| `send_message` を上司以外の内部 Anima へブロック（`CommandChainViolation`） | 上司以外の内部 Anima へのメッセージ送信をブロック。コンテンツ内のプロンプトインジェクションも検知するため |
| `append_episode` で OVERDUE / O/P/R ヘッダパターンを含むエントリを拒否 | vectordb インデックス前に汚染エントリ（OVERDUE や O/P/R ヘッダパターンを含むもの）を排除するため |

### 2-b. Rule of Two（web_fetch × execute_command の相互排除）
**今セッション実施**

| 変更内容 | なぜ変更したか |
|---------|--------------|
| `handle()` 内で同一サイクルの `web_fetch` + `execute_command` 併用を `RuleOfTwoViolation` でブロック | NVIDIAの"Rule of Two"記事を起点に評価。「cicchi が Rule of Two を超える」ことが判明し、プロンプトインジェクション → RCE チェーンを防ぐために実装（ユーザー指示 + セキュリティ評価レポート `security_rule_of_two.md`） |

### 2-c. インジェクション検知モジュール
**コミット** `f37b7e96`

| 変更内容 | なぜ変更したか（コミットより） |
|---------|------------------------------|
| `core/execution/_sanitize.py` — inbox 受信メッセージのインジェクションパターン検知 | 「`_sanitize.py`: インジェクション検知パターンを拡張」（`_anima_inbox.py` 内で使用し、疑わしいコンテンツに警告バナーを付与） |

---

## 3. ⏱ タスク管理強化

**コミット** `53d04ab3`

| 変更内容 | なぜ変更したか（コミットより） |
|---------|------------------------------|
| `auto_block_stale_tasks()` — 2時間以上 in_progress のタスクを自動 blocked 化 | inbox で新しい指示を受信した Anima が、それ以前のタスクの blocked/failing 状態が `current_task.md` に残っていて動けなくなる「スタックタスク麻痺」を防ぐため |

---

## 4. 📨 メッセージング・セッション管理の修正

| コミット | 変更内容 | なぜ変更したか（コミットより） |
|---------|---------|------------------------------|
| `57bfa3b5` | inbox 開始前に `replied_to.jsonl` をクリア | 古いエントリが原因で「already sent」の偽陽性エラーが発生し、委譲レポート（rue → cicchi パイプライン）がブロックされていたため |
| `28580d6a` | heartbeat と inbox の reply 追跡を全セッションリセットに変更 | heartbeat がリセットに「background」セッション、実際の送信に「chat」セッションを使っており、古い cicchi/kuro エントリが `_replied_to["chat"]` に残って後続の inbox 実行に漏れていたため |
| `bcdd10ea` | heartbeat.md を修正し空のステータス報告を禁止 | Anima が `send_message` で `HEARTBEAT_OK` を送信することで `cascade_limiter` を消費し尽くしていたため |
| `c18395c5` | クールダウン/レート制限エラーメッセージに「システム障害ではない」を明記 | ツールのクールダウン/レート制限エラーを受信した Anima が「システム障害」と誤解して上司へ緊急報告するループを防ぐため |
| `c2292492` | 処理済み inbox メッセージを heartbeat プライミングから除外 | 完了済みの inbox セッション内の `message_received` エントリが heartbeat システムプロンプトへ注入され、LLM が完了済みの委譲からタスクを再作成していたため（例：午前のパイプライン完了後2時間後に kuro が Step 2 を再実行） |

---

## 5. ⚙️ モデル・設定改善

| コミット | 変更内容 | なぜ変更したか（コミットより） |
|---------|---------|------------------------------|
| `b09be8f5` | `gemini/*` を Mode A パターンに追加 | rue が Mode B（テキストベースのツール解析）で動いており、Mode B では1レスポンスにつき1ツール呼び出ししか抽出できないため、rue の inbox セッションが `web_search` 1回で終了し `send_message` やファイル書き込みが実行されなかった。**これがパイプライン繰り返しストールの根本原因だった** |
| `b09be8f5` | `PrimingConfig.excluded_tools` を追加 | コードコメント: 「これらのツールの tool_use エントリを priming から除外（低シグナルのシステム操作のため）」 |
| `b09be8f5` | `heartbeat_offset_minutes` フィールド追加 | コードコメント: 「CRC32ベースのオフセットを上書きするため」 |

---

## 6. 🛠 ツール・ディスパッチの修正

**コミット** `4c7447a9`

| 変更内容 | なぜ変更したか（コミットより） |
|---------|------------------------------|
| `dispatch.py`: インポート失敗モジュールをスキップ | 失敗したツールモジュール（例: gmail のインポートエラー）で即座にエラーを返すのではなくスキップし、後続のツール（web_search）をロードできるようにするため |
| `handler_perms.py`: 書き込みパーミッション確認を「書ける場所」セクションに変更 | 読み取り許可セクションのみチェックしていたため `output/` への書き込みで `PermissionDenied` が発生していた。これを修正するため |
| `web_search.py`: `count` を `int` に強制変換 | LLM が文字列として渡す場合があり、`min`/`max` の比較で `TypeError` が発生していたため |

---

## ⚠️ 未コミット変更（2026-03-24 時点）

以下は `git diff HEAD` で確認した作業中の変更。次回コミット時に反映予定。

---

## 7. 🔗 パイプライン追跡（pipeline_id / task親子リンク）

**変更ファイル**: `core/_anima_inbox.py`, `core/_anima_heartbeat.py`, `core/tooling/handler_comms.py`, `core/tooling/handler_org.py`, `core/memory/task_queue.py`, `core/messenger.py`

| 変更内容 | なぜ変更したか |
|---------|--------------|
| `inbox` で受信メッセージの `pipeline_id` を引き継ぐ。なければ新規発番 | cicchi→kuro の委任チェーンを1つの `pipeline_id` で追跡し、パイプラインUIで「どの指示が起点か」を可視化するため |
| `heartbeat` 起動時に `pipeline_id` を新規発番 | heartbeat 起点の委任も pipeline として追跡できるようにするため |
| `TaskEntry` に `parent_task_id` / `root_task_id` フィールドを追加 | タスクの親子ツリーを構築し、委任の連鎖（cicchi→kuro→…）を追跡するため |
| `delegate_task` で `parent_task_id` / `root_task_id` を引き継いで子タスクを作成 | 親タスクと子タスクを紐付け、ツリー表示・完了ロールアップを可能にするため |
| `messenger.send()` に `task_id` / `pipeline_id` パラメータを追加 | メッセージに task_id を添付して受信側が `in_progress` に自動遷移できるようにするため |
| `activity_log` の `message_sent` / `message_received` に `task_id` / `pipeline_id` を記録 | パイプラインUIがイベントとタスクを紐付けられるようにするため |
| `handler_org.py`: `delegate_task` のイベント種別を `tool_use` → `task_delegated` に変更し `from_person`/`to_person` を追加 | パイプラインUIで「cicchi→kuro委任」が起点として正しく表示されていなかったため（kuroが起点に見えていた問題の修正） |

---

## 8. 💤 アイドル時ハートビートスキップ

**変更ファイル**: `core/_anima_lifecycle.py`

| 変更内容 | なぜ変更したか |
|---------|--------------|
| `_is_heartbeat_idle()` メソッドを追加。unread inbox / recovery_note / background通知 / active task が全てない場合 `True` を返す | 何もすることがないのに LLM API を呼び出してトークンを消費するのを防ぐため |
| `run_heartbeat()` の冒頭で `_is_heartbeat_idle()` をチェックし、アイドル時は API 呼び出しをスキップして `HEARTBEAT_OK` を返す | 無駄なAPI呼び出しを削減し、レート制限・コストを低減するため |

---

## 9. 📨 send_message 委任時のタスク自動生成

**変更ファイル**: `core/tooling/handler_comms.py`

| 変更内容 | なぜ変更したか |
|---------|--------------|
| `send_message(intent="delegation")` 実行時、アクティブな `task_id` がなければ委任先の task_queue にタスクを自動生成する | `delegate_task` を使わず `send_message` で委任した場合でも task_queue に記録が残るようにするため。パイプラインUIとの整合性を保つ |

---

## 10. 📬 inbox: task_id に基づく自動 in_progress 遷移

**変更ファイル**: `core/_anima_inbox.py`

| 変更内容 | なぜ変更したか |
|---------|--------------|
| inbox 受信メッセージに `task_id` が含まれる場合、該当タスクのステータスを `pending` → `in_progress` に自動更新 | タスクが委任されて受信側のinboxに届いた時点でステータスが自動遷移するようにするため |

---

## 11. 🔒 Rule of Two（未コミット分の整備）

**変更ファイル**: `core/tooling/handler.py`

| 変更内容 | なぜ変更したか |
|---------|--------------|
| `ToolHandler` に `_rule_of_two_used: set[str]` を追加 | `web_fetch` と `execute_command` の使用履歴を同一サイクル内で追跡するため |
| `reset_session_id()` 時に `_rule_of_two_used` をクリア | サイクル間で状態が持ち越されないようにするため |
| `_RULE_OF_TWO_PAIRS` 定数で排他ペアを定義し、`handle()` 冒頭でブロック | プロンプトインジェクション → コード実行のチェーン（RCE）を防ぐため |

---

## 12. 🧠 埋め込みモデルの外部API対応

**変更ファイル**: `core/memory/rag/singleton.py`

| 変更内容 | なぜ変更したか |
|---------|--------------|
| `OpenAICompatibleEmbeddingModel` クラスを追加 | LM Studio など OpenAI 互換の `/v1/embeddings` エンドポイントを埋め込み生成に使えるようにするため。SentenceTransformer を使わずローカルモデルで代替できる |
| `RemoteEmbeddingModel` クラスを追加 | AnimaWorks メインサーバーの `/api/internal/embed` に委譲するクライアント。ワーカープロセスがモデルを直接ロードしなくて済む（起動コスト約6秒を回避） |
| `get_embedding_model()` に優先順位を追加: ① `rag.embedding_api_base`（LM Studio）→ ② `ANIMAWORKS_EMBEDDING_SERVER_URL`（内部サーバー）→ ③ ローカル SentenceTransformer | config.json の1設定でモデルバックエンドを切り替えられるようにするため |

---

## 13. 🔧 統合（Consolidation）のカスタムAPI対応

**変更ファイル**: `core/memory/distillation.py`

| 変更内容 | なぜ変更したか |
|---------|--------------|
| `procedural_distill()` / `weekly_pattern_distill()` に `api_base` / `api_key` パラメータを追加 | `ConsolidationConfig.llm_api_base` / `llm_api_key` を読み込み、LM Studio などカスタムエンドポイントで distillation を実行できるようにするため |
