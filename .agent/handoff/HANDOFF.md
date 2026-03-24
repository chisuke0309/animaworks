# HANDOFF - 2026-03-24 (夜セッション終了)

## 使用ツール
Claude Code (claude-sonnet-4-6) / worktree: charming-knuth

---

## 現在の状態

### AnimaWorks稼働状況
- 全anima（cicchi/rue/kuro/sora）稼働中
- ミッション: ペット・グルーミング＋エコ・サステナブル生活術
- 旧コンテンツ（AI/RPA時代）は完全クリーンアップ済み

---

## 完了済み（このセッション）

- [x] **Workspace「組織」ボタン → 組織目標パネル実装**
  - `org-dashboard.js`: 「組織」タイトルを `🎯` ボタンに変更
  - クリックで goals panel をオーバーレイ表示（position: absolute; inset: 0）
  - `/api/common-knowledge/organization/goals.md` を読み書き
  - マークダウン表示・編集・保存機能つき
  - CSS追加: `.org-goals-btn`, `.org-goals-panel`, `.org-goals-table` 等
  - `.org-dashboard` に `position: relative` 追加（overlay基準）

- [x] **main sidebar から「🎯 組織目標」メニュー削除**
  - `index.html` から該当 `<li>` を削除（Workspaceから参照可能なため）

- [x] **common_knowledge/00_index.md に goals.md を登録**
  - `organization/` セクション先頭（最重要）に追記
  - 「意思決定・優先順位付けの基準として常に参照すること」と明記
  - キーワード索引に「目標, KPI, 収益, マイルストーン, 月次, 数値目標」追加

---

## 未完了（次セッション以降）

### 高優先度
- [ ] **permissions.mdホワイトリスト化**（トークン削減）
  - 現状 `all: yes` で毎heartbeat ~20,000 chars のツールスキーマが注入されている
  - 各animaに必要なツールのみに絞る（`/reorganize-team` Step 2-3 参照）

- [ ] **Telegram承認フローの動作確認**
  - x_post_approval.pyのsys.path修正済み → 次回投稿で `No module named 'core'` が解消されるか確認
  - injection.mdに「OK/ok/はい/承認 → x_post_execute_pending」の明示ルールを追加すること（要確認）

### 中優先度
- [ ] **パイプライン詳細パネルのコンテンツ表示**（JS実装）
  - CSS修正済み。明細クリック→メッセージ本文をパネルに表示するJS実装が残り

### 低優先度
- [ ] **Xプロフィール変更**: ユーザーが手動でTrinityDoxのアカウント名・bio変更（未実施）
- [ ] **consolidation/distillationモデル切り替え**: Qwen3.5-4B（LM Studio）検討中

---

## 重要な技術メモ

### 組織目標ファイルの流通経路
- **ファイル**: `~/.animaworks/common_knowledge/organization/goals.md`
- **UI**: Workspace → 「組織 🎯」ボタン → goals panel で表示・編集
- **API**: `GET/PUT /api/common-knowledge/organization/goals.md`
- **Animaからのアクセス**: `read_memory_file(path="common_knowledge/organization/goals.md")`
- **RAG検索**: `search_memory(query="目標 KPI 収益", scope="common_knowledge")` でヒット
- **00_index.md**: 登録済み → 迷ったときにも自動参照される

### x_post_approval.py スロット仕様
```python
# 朝8時枠
x_post_request_approval(text="...", slot="morning")
x_post_execute_pending(slot="morning")

# 夕17時枠
x_post_request_approval(text="...", slot="evening")
x_post_execute_pending(slot="evening")
```
ファイル: `~/.animaworks/animas/cicchi/state/pending_x_post_{slot}.json`

### 旧コンテンツ汚染の根本原因（教訓）
- `shortterm/chat/archive/` — **最も見落としやすい**。大量のセッションアーカイブが蓄積し、heartbeatコンテキストに混入する
- `state/` 直下のmdファイル（x_post_restore_report.md等）— 名前が汎用的でも中身が旧コンテンツの場合あり
- `knowledge/revenue_strategy.md` 等 — ミッション変更後も残りやすい

### cicchi cronスケジュール
| 時刻 | 内容 |
|------|------|
| 08:00 | 朝の固定投稿（morning枠実行） |
| 09:00 | 日次オーケストレーション（evening枠コンテンツ制作） |
| 17:00 | 夕方の固定投稿（evening枠実行） |
| 21:00 | 日次レビュー＆翌朝準備（翌日morning枠コンテンツ制作） |

### anima構成（現在）
| anima | モデル | ロール |
|-------|--------|--------|
| cicchi | claude-sonnet-4-6 | オーケストレーター |
| rue | claude-haiku-4-5-20251001 | ニッチ調査 |
| kuro | claude-haiku-4-5-20251001 | コンテンツ制作 |
| sora | claude-haiku-4-5 | ビジュアル生成 |

### 読むべきドキュメント（理解の手引き）
- **起動・記憶の仕組みを理解したい**: `docs/brain-mapping.ja.md`（247行、推奨）
- **詳細なメモリシステム**: `docs/memory.ja.md`（792行）
- **システム全体の機能**: `docs/SYSTEM_OVERVIEW.md`（634行）
