# HANDOFF - 2026-04-24 夕

## 使用ツール
Claude Code (Opus 4.7 / 1M context) + Codex CLI (`codex exec --full-auto`)

## 作業対象プロジェクト
AnimaWorks — cicchi HB 4段化 + ブラックボード導入 の Codex バグレビューと修正

---

## 今回セッションで実施したこと

### 1. Codex をMCP登録 + ローカル CLI で一発レビュー実行
- `~/.claude/mcp.json` に `codex` を追加（次回セッションから MCP ツール利用可能に）
- 今回は再起動不要な `codex exec --full-auto --skip-git-repo-check -` でレビュー実行
- `/tmp/codex_review_prompt.md` に依頼書、`/tmp/codex_review_result.md` に結果保存

### 2. Codex からの指摘 10件（重大度別）
- 🔴 Critical × 3：permissions whitelist漏れ・episode未sanitise・regex強度不足
- 🟡 Major × 4：run_cron_command の3点保守欠落・API失敗時の0上書き・tmp衝突・Contract日付境界
- 🟢 Minor × 3：複数CONTRACT/placeholder吸い込み・goals誤マッチ・UTF-8バイト境界

### 3. 10件中9件を修正完了（M1のみ後回し）
ファイル別:
- `core/_anima_heartbeat.py`: `_sanitize_hb_summary()` 共通化、regex強化（h1-h4/絵文字/bold対応）、Contract抽出の複数ブロック・placeholder排除、`_load_latest_contract()` の日付境界判定、`_truncate_utf8()` でバイト境界trimming
- `core/tools/blackboard_writer.py`: 失敗時の前回値フォールバック + stale marker、tmp ファイルに PID + monotonic_ns suffix、goals.md の `## X事業部` セクション限定パース
- `~/.animaworks/animas/cicchi/permissions.md`: `blackboard_writer: yes` 追加

### 4. 修正後の統合テスト（全て通過）
- sanitizer: h1-h4 + emoji + bold + CJK 全パターン剥がし確認
- Contract: 複数ブロック → 最後の非プレースホルダ採択
- goals.md: 別表に `Xフォロワー数` が混入しても X事業部 側だけを拾う
- UTF-8 境界: 15000バイト日本語文字列 → 8206バイトに安全トリム
- X API 正常: `followers: 9, stale: False`
- X API 失敗（無効トークン）: `followers: 9, stale: True` で前回値保持、markdown に stale 警告追記

---

## 現在のタスクと進捗

- [x] Codex MCP 登録（次回から利用可能）
- [x] Codex バグレビュー実行（結果は `/tmp/codex_review_result.md`）
- [x] Critical 3件修正
- [x] Major 4件中 3件修正
- [x] Minor 3件修正
- [x] 全修正後の統合テスト
- [ ] **M1: `run_cron_command` で task_queue 3点保守が呼ばれない既存構造問題**（次回以降）
- [ ] **git コミット**（初期実装 + 修正を含む）
- [ ] **cicchi の次回HB実機観察**（4/25 朝以降）

---

## 試したこと・結果

### ✅ 成功したアプローチ
- **Codex を `codex exec review --uncommitted` で呼ぼうとしたが `[PROMPT]` と `--uncommitted` は排他** → `codex exec --full-auto` でフル依頼書を渡して成功
- **`_sanitize_hb_summary()` をモジュール関数として共通化** → heartbeat_end と episode 保存の両経路で同一処理に
- **Contract 日付比較は ISO文字列の先頭10文字で**十分堅牢（`(e.ts or "")[:10]`）
- **tmp ファイルに PID + monotonic_ns** で並行実行耐性確保
- **M2 のフォールバック**：既存 blackboard 本体から前回値を regex で再パースする方式。別 state ファイル不要

### ❌ 失敗・気づき
- Codex MCP 登録後、ToolSearch で `codex` を検索してもまだ見えない（**Claude Code 再起動が必要**）
- `codex exec review --uncommitted` は prompt と共存できないオプション設計
- 初期実装で **`result.summary[:500]` → episodes 直書き** という致命的ミスがあった。sanitizer は heartbeat_end にしか適用していなかった（Codex C2 の核心）

---

## 次のセッションで最初にやること

1. **git コミット作成**
   - 初期実装（Per-Anima テンプレ・ブラックボード・Contract）+ Codex 指摘修正 をまとめる
   - または 2 コミットに分ける（初期実装 / バグ修正）かユーザー判断
2. **cicchi の実機HB観察**
   - 最初の HB 実行で `prompt_logs/cicchi_*.json` を開き、以下を目視確認
     - ブラックボード本体（フォロワー9人・目標100人・残91人・15.17人/day ペース）が注入されている
     - `yesterdays_contract_block` は初回なので空
   - HB 終了後の `activity_log/YYYY-MM-DD.jsonl` で `heartbeat_contract` タイプが記録されているか確認
3. **2日目観察**
   - 翌朝HBで `{yesterdays_contract_block}` に前日の Contract が注入されるか確認
   - `episodes/YYYY-MM-DD.md` に verbose 5段出力が**漏れていない**こと（sanitizerが効いている証左）
4. **M1 の扱いを決める**
   - `run_cron_command` での task_queue 保守呼び出しを追加するか、既存構造問題として後回しか
   - cicchi は HB 有効なので当面は影響小さい

---

## 注意点・ブロッカー

### Codex MCP
- `~/.claude/mcp.json` に `codex` 追加済み。Claude Code 再起動後に `mcp__codex__*` が見える
- CLI 直起動（`codex exec`）で今回は代替済み。再起動不要な手段が残っている

### 修正内容の検証前提
- **7:00 cron を待たないと blackboard_update_org_status の cron 経路は確認できない**
- 手動では `uv run python -c "from core.tools.blackboard_writer import update_org_status; update_org_status()"` で発動可能

### 既知の残課題（Codex M1）
- `_anima_lifecycle.py::run_cron_command()` で task_queue 3点保守（auto_block/auto_resolve/maybe_compact）が呼ばれない
- `inbox_only` / `off` モード Anima の stale task が積もるリスク
- 今回の cicchi は HB 有効なので影響なし。maru チーム再稼働時までに対応推奨

### maru チーム状態（前回から変わらず）
- maru / chiro / tama は `enabled: false` で停止中
- cicchi 検証効果確認後、同パターン（4段+ブラックボード）を適用する方針

### Kyoka事業部（前回から変わらず）
- rin / kiri / sumi 停止中
- Kyoka Scenarios DB と 3 シナリオは保持、素材量産・投稿戦略は保留

### yomi
- 毎日 20:03 CrowdWorks巡回、正常稼働中
