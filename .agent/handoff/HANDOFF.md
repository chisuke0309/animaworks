# HANDOFF — 2026-04-12 セッション（夜）

## 使用ツール
Claude Code（Sonnet 4.6）

## 作業対象プロジェクト
animaworks（knowledge管理改善・ドキュメント更新）

---

## 現在のタスクと進捗

### ✅ episodesローテーション自動化

- 毎日03:30 JSTに全animaのepisodes/を7日分のみ保持するcronを実装済み
- 既存の古いepisodes（04-05以前 + recoveredファイル）を手動で一括削除済み
- `core/supervisor/_mgr_scheduler.py` に `_run_episodes_rotation()` 追加・登録済み

### ✅ knowledgeファイル自動ローテーション（Phase 1・2）

`core/supervisor/_mgr_scheduler.py` に2メソッド追加:
- `_run_knowledge_rotation()`: 毎日03:35 JST、ファイル名に日付パターン（YYYY-MM-DD / YYYYMMDD）を含むknowledgeファイルを7日後に自動削除（archive/サブディレクトリも対象）
- `_run_engagement_log_rotation()`: 毎月1日04:00 JST、engagement_log.mdの## YYYY-MM-DDセクションのうち30日超えを削除

サーバー再起動後、ログで両cronの登録を確認済み。

### ✅ 週次knowledge棚卸し（Phase 3）

- `~/.animaworks/animas/cicchi/cron.md`: 戦略レビュー（月水金）のStep2・Step4に月曜限定の棚卸し指示を追加
  - rue/kuro/chiro/soraへDMで棚卸し依頼
  - 棚卸しの本質: 有効な知識をテーマ別統合ファイルに書き直す（単なる要約禁止）
  - call_human報告に棚卸し結果サマリーを追加
- `~/.animaworks/animas/maru/cron.md`: 週次レビュー（月曜）に同様の棚卸し指示を追加
  - tama/chiroへDMで棚卸し依頼
  - maru自身のknowledge棚卸しも実施
  - call_humanでTikTok事業部の結果を報告

### ✅ ドキュメント更新

以下4ファイルに今回の新機能を追記:
- `docs/memory.md`: Active Forgettingセクション末尾に「Automated Knowledge File Rotation」セクションを新設
- `docs/memory.ja.md`: 同上の日本語版
- `docs/features.md`: Post-v0.2 Enhancements → Memory Systemに2エントリ追加
- `docs/features.ja.md`: 同上の日本語版

---

## 試したこと・結果

- ✅ episodesローテーション（03:30 JST）をモデルに、knowledgeローテーション（03:35 JST）を同パターンで実装
- ✅ 日付パターン: ISO形式 `(\d{4}-\d{2}-\d{2})` を優先、連結形式 `(?<!\d)(\d{8})(?!\d)` をフォールバック
- ✅ cicchi/maruの両オーケストレーターに棚卸しを組み込み（「maruを忘れるな」というユーザー指摘で修正）
- ✅ 棚卸しは「要約ではなく有効な情報の再構成」という本質をcron.mdに明記（ユーザー指摘で設計修正）

---

## 次のセッションで最初にやること

1. **Xアカウントサスペンド解除確認**
   解除されたら:
   - `hana/cron.md`: 4つのscheduleを元に戻す（10:00/15:00/20:00/木17:00）
   - `cicchi/cron.md`: 3つのscheduleを元に戻す（08:00/17:00/22:00）
   - `.env`のTWITTER_*が有効か再確認

2. **月曜棚卸しの初回実行確認**（次の月曜 2026-04-13 10:00）
   - cicchi/maruから各メンバーへ棚卸し指示DMが飛ぶか確認
   - 各animaがknowledgeファイルを統合・削除して報告するか確認

3. **yomi: CrowdWorks新カテゴリ検討**
   - 現在のSEO記事巡回は停止中（ヒット少なく一時停止）
   - 別の案件カテゴリを検討してcron.mdを更新する

4. **caption_prefix初回データ確認**
   - maruの次回納品後、`post_plan_log.jsonl`にcaption_prefixが入っているか確認

---

## 注意点・ブロッカー

- **最大のブロッカー**: @TrinityDox_JP Xアカウントサスペンド中。解除まで投稿・エンゲージメント・計測すべて停止
- pendingに溜まったコンテンツは復旧後そのまま使えるが、鮮度が落ちる可能性あり
- 月曜棚卸し初回: cicchi/maruが各animaからの報告を待ってcall_humanを送る設計のため、全メンバーが応答するまでセッションが長くなる可能性あり

---

## 変更ファイル一覧

| ファイル | 変更 |
|----------|------|
| `core/supervisor/_mgr_scheduler.py` | `_run_knowledge_rotation()` / `_run_engagement_log_rotation()` 追加、`_setup_system_crons()` に登録 |
| `~/.animaworks/animas/cicchi/cron.md` | Step2・Step4に月曜限定の棚卸し指示を追加 |
| `~/.animaworks/animas/maru/cron.md` | 週次レビューに月曜限定の棚卸し指示を追加 |
| `docs/memory.md` | Automated Knowledge File Rotationセクション新設 |
| `docs/memory.ja.md` | 自動ナレッジファイルローテーションセクション新設 |
| `docs/features.md` | Memory Systemに2エントリ追加 |
| `docs/features.ja.md` | 記憶システムに2エントリ追加 |

---

## モデル構成

| anima | モデル | ロール |
|-------|--------|--------|
| maru | claude-sonnet-4-6 | TikTok事業部リーダー |
| cicchi | claude-sonnet-4-6 | X事業部オーケストレーター |
| tama | claude-sonnet-4-6 | カルーセル制作 |
| chiro | claude-haiku-4-5 | トレンド調査 |
| kuro | claude-haiku-4-5 | コンテンツ制作 |
| sora | claude-haiku-4-5 | ビジュアル生成 |
| hana | claude-haiku-4-5 | エンゲージメント担当 |
| rue | claude-sonnet-4-6 | ニッチ調査 |
| yomi | claude-sonnet-4-6 | general |
