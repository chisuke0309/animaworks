# HANDOFF - 2026-04-28（夜・セッション終了）

## 使用ツール
Claude Code（Sonnet 4.6 に切り替え済み）

## 作業対象プロジェクト
AnimaWorks — Kyoka事業部 自律パイプライン実装（P2 完了・P3 待ち）

---

## 本日の達成

### 1. TikTok / Instagram 初投稿
- TikTok `@kyokakisaragi` / Instagram `@kyokakisaragi.ai` 開設
- scenario_003（青もみじの古刹）を両プラットフォームに同日投稿・審査通過
- Notion DB / video_inventory.md / kyoka_unit.md 更新済み

### 2. P2 パイプライン実装完了
新規ツール（**未コミット**）：
- `core/tools/kyoka_image.py` — gpt-image-1 ラッパー（将来用・現在は画像生成に呼び出さない）
- `core/tools/_kyoka_prompt_template.py` — 固定キャラ仕様・プロンプト組み立て・validator
- `core/tools/kyoka_pipeline.py` — シナリオ生成LLM → Notion登録の一気通貫

### 3. 方針転換（重要）
**API コスト問題（本日だけで $6 消費）のため、画像生成は自動化しない。**

| 工程 | 担当 |
|------|------|
| トレンド調査・テーマ決定 | kiri/rin（Anima・自動） |
| シナリオ生成・プロンプト生成 | kyoka_pipeline（LLM・自動） |
| Notion 全フィールド登録 | kyoka_pipeline（自動） |
| **6フレーム画像生成** | **chisuke 手動（ChatGPT GUI）** |
| 動画生成（Seedance） | chisuke 手動 |
| 投稿 | chisuke 手動 |

`kyoka_image.py` は将来のために残す（コスト問題が解決したら再活用）。

### 4. scenario_004/005 の Notion プロンプト更新済み
Gemini の分析で判明した構造的問題（参照画像の強制拘束が frame_prompts から欠落）を修正。

#### 修正内容（`_kyoka_prompt_template.py`）
- `FRAME_PROMPT_PREFIX` に `[Reference image uploaded: portrait of a Japanese woman named Kyoka]` と `CRITICAL: Match the reference image's exact face shape, sharp jawline, youthful structure...` を追加
- `KYOKA_FIXED_CHARACTER_SPEC` に年齢・骨格明示を追加：`Age: late twenties — preserve youthful firmness, sharp jawline. Do NOT round the face.`
- `FORBIDDEN_TERMS` から否定形で使われる語（furrowed/scowl 等）を削除し、本当に問題の語（fierce/angry/grim）だけに絞った

#### 更新済み Notion レコード
- scenario_004「鏡花、梅雨の縁側に端居す」: https://www.notion.so/kyoka_scenario_004-3501158c25dc816e84a9e80aa32a4ea4
- scenario_005「鏡花、月明かりの床の間に座す」: https://www.notion.so/kyoka_scenario_005-3501158c25dc812aa0a3c86e917d6fd2

### 5. アカウント情報（kyoka_unit.md に記録済み）
- TikTok: `@kyokakisaragi`
- Instagram: `@kyokakisaragi.ai`
- Google アカウント: macOS キーチェーン参照
- Bio: `鏡花 — Kyoka / She walks where gods still linger. / 🎋 Kyoka — Japanese mystery × AI`

---

## 次のセッションで最初にやること

### 1. scenario_004/005 の画像生成確認（chisuke 手動）
ChatGPT GUI で以下の手順：
1. Notion の scenario_004 or 005 を開く
2. **「GPT Image Prompt」フィールド**をコピー
3. `kyoka_closeup_001_start.jpg` を参照画像としてアップロード（`~/.animaworks/common_knowledge/tiktok_templates/kyoka/assets/`）
4. プロンプトを貼り付けて画像生成
5. 品質OK → P3 着手 / NG → プロンプト追加修正

### 2. 品質OKなら P2 をコミット & push
```bash
# P1 テストファイルを先に破棄
rm -f ~/Projects/animaworks/scripts/kyoka_image_test.py
rm -f ~/Projects/animaworks/scripts/_kyoka_p1_prompts.json
rm -rf ~/Projects/animaworks/tmp/

# コミット対象
git add core/tools/kyoka_image.py
git add core/tools/_kyoka_prompt_template.py
git add core/tools/kyoka_pipeline.py
git add .agent/  # units/ / handoff/ の更新

git commit -m "feat(kyoka): P2 pipeline — scenario generation + Notion registration (images manual)"
git push fork main
```

### 3. P3 着手（cicchi 構造を Kyoka に複製）
詳細は `/Users/chisuke/.claude/plans/c-ok-anima-dynamic-blum.md` 参照。

優先順：
1. rin/kiri/sumi に `heartbeat.md`（cicchi 構造を踏襲）作成
2. rin の knowledge 初版：`weekly_strategy.md` / `theme_registry.md` / `tiktok_log.md`
3. kiri の knowledge 初版：`market_pulse_kyoka.md`
4. `shared/blackboard/kyoka_status.md` + `blackboard_writer.py` 拡張
5. rin/kiri/sumi の `injection.md` / `cron.md` / `permissions.md` を P3 用に更新
6. `status.json` 全員 `enabled: true`
7. lint + cron パース + サーバー再起動 + 動作確認

---

## 注意点

### コスト管理
- kyoka_pipeline は LLM（claude-sonnet）のみ使用 → 1シナリオ約 $0.02
- 画像生成は ChatGPT GUI（月額プランの範囲内）
- gpt-image-1 API は kyoka_image.py に保持するが**呼び出さない**

### Anthropic API キー
- `.env` と `~/.animaworks/config.json` の `credentials.anthropic.api_key` 両方を更新済み（2026-04-28）
- 次回ローテート時は**両方**を必ず更新すること

### Notion インテグレーション
- Kyoka Scenarios DB（f1d407fcb3d94ca78cd81ddbe2c11d67）に AnimaWorks インテグレーションを接続済み（2026-04-28）

### モデル
- Claude Code のモデルは **Sonnet 4.6** に切り替え済み（`/model sonnet[1m]`）

---

## 関連ファイル

| ファイル | 内容 |
|---------|------|
| `~/.claude/plans/c-ok-anima-dynamic-blum.md` | P2/P3 全体実装計画 |
| `core/tools/kyoka_image.py` | gpt-image-1 ラッパー（将来用・現在呼び出しなし） |
| `core/tools/_kyoka_prompt_template.py` | **キャラ仕様の正規化ファイル・画像品質の要** |
| `core/tools/kyoka_pipeline.py` | シナリオ生成→Notion登録 |
| `~/.animaworks/common_knowledge/tiktok_templates/kyoka/assets/kyoka_closeup_001_start.jpg` | 参照画像（顔の基準） |
| `~/.animaworks/animas/cicchi/heartbeat.md` | P3 で rin 用 heartbeat の雛形 |
| `~/.animaworks/animas/cicchi/knowledge/weekly_strategy.md` | rin 用 weekly_strategy の雛形 |
| Notion Kyoka Scenarios DB | https://www.notion.so/f1d407fcb3d94ca78cd81ddbe2c11d67 |
