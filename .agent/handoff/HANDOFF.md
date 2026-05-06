# HANDOFF — 2026-05-06 13:25

## 使用ツール

Claude Code（VSCode拡張・Opus 4.7 1M context）

## 作業対象プロジェクト

**animaworks** — 業務AI 体制での X 投稿テストと、cicchi 事業部の情報源強化

## 現在のタスクと進捗

- [x] **rue 調査ツール群の実動作確認**: bird CLI / Exa / Jina Reader / mcporter / web_search は OK、yt-dlp（YouTube 署名失敗）と Reddit JSON（403）は使用不可と判明 → injection から削除
- [x] **ai-research-hub を rue の一次ソースに位置付け**: 既存リポジトリ `~/Projects/ai-research-hub/`（毎朝6:48 までに5ソースを Obsidian Vault に保存）への参照を組み込み
- [x] **`topic_selection_criteria.md` 新規作成**: 4層スコアリング（必須フィルター → 5軸×5点採点 → ジャンル偏り回避 → 最終判断、15点以上で候補）
- [x] **cicchi cron.md / injection.md / agent-reach-tools.md / rue injection.md / 両 permissions.md 更新**: ai-research-hub 参照フロー全面導入
- [x] **X プロフィール書き換え案を提示**（chisuke が反映済み）
- [x] **Substack 兼用ヘッダー画像プロンプト3案を提示**（3:1 / 1500×500、左下プロフィール画像との重なり配慮）
- [x] **業務AI 体制での第1号テスト投稿を完成**: ネタ選定（GitLab AIパラドックス、スコア25/25満点）→ 構成案 → 本文（フックB案・718文字）→ 画像（FLUX 16:9 + Pillow 日本語オーバーレイ）→ pending保存（id `20260506T131722_evening`、品質9.3/10）→ 承認 API 経由で approved に
- [x] **旧体制（ペット）の pending 2本を削除**: `20260430T211122_morning`（パピヨン）/ `20260430T213350_evening`（パピヨン）
- [x] **unit ファイル更新**: `x_unit.md`（業務AI 体制での初投稿準備完了・教訓追記）

## 試したこと・結果

### ✅ 成功

- **rue 調査ツール実動作テスト**: bird search で業務AI 投稿が即取得、Exa で「パナソニック18.6万時間削減」など定量データ即取得、Jina Reader で Anthropic News を Markdown 化、mcporter で5サーバー稼働確認
- **ai-research-hub 連携**: chisuke 既存リポジトリの出力を rue の最優先情報源に位置付け、ハルシネーション抑制 + 検索負荷軽減を狙った設計に変更
- **topic_selection_criteria.md による初スコアリング**: 5ファイル → 上位3候補抽出 → GitLab AIパラドックスが25/25満点で採用
- **画像生成2段階フロー**: FLUX で「ツール散乱」風の抽象背景を生成 → Pillow で「週7時間が消えている。/ GitLabが指摘するAIパラドックス」を白文字中央オーバーレイ → 約558KBの完成画像
- **`x_post_save_pending` 直接呼び出し**: Python 関数を直接 import して呼び、品質スコア9.3/10 で pending 保存成功
- **承認 API**: `POST /api/approvals/posts/{id}/approve` で approved に切り替え成功

### ❌ 失敗・気づき

- **`.venv/bin/python` では fal_client が未インストール**: シンボリックリンクで miniforge を指していても site-packages は別。`/opt/homebrew/Caskroom/miniforge/base/bin/python` を直接呼ぶ必要あり。`Pillow` も同様で `pip install Pillow` を miniforge 側に実施
- **承認 API パスを最初に間違えた**: `/approvals/posts/...` で 405。正しくは `/api/approvals/posts/.../approve`。`/openapi.json` で確認可能
- **同 slot に approved が残っていると新規 pending が強制 pending 化される**: queue backup 防止の安全装置。旧体制の approved 投稿（パピヨン）が残っていたため最初は強制 pending になった → 旧体制の pending 2本を削除して解消
- **生成途中で背景画像が一度消失**: tmp ディレクトリの `.DS_Store` 以外が消えていた（原因不明、誰かのクリーンアップ動作？）→ 再生成して対応
- **FLUX に日本語直書きさせるのは無理**: 過去の sora ノウハウ通り、FLUX 背景 + Pillow オーバーレイの2段階が定石

## 次のセッションで最初にやること

（このセッションで完了。次回のタスクは未定）

ただし時系列で発生する確認事項：

1. **本日17:00 に第1号投稿が自動発射されるはず**（cron `x_post_execute_pending slot=evening`）— pending JSON の status が `posted` になり tweet_id が記録されているか
2. **22:00 にエンゲージメント計測**（cron `x_post_update_engagement`）— impressions / likes / RTs

## 注意点・ブロッカー

- **本日17:00 発射予定の第1号投稿**: id `20260506T131722_evening`、status `approved`、業務AI 体制での記念すべき1本目。失敗した場合は `~/.animaworks/logs/` を確認
- **cicchi 事業部 5 体は依然 enabled: false**: 今回の投稿は私（Claude）が代行で `save_pending_post` を直接呼んだ。Anima 駆動での自動投稿は次回以降の検証
- **maru 事業部は稼働継続**: cicchi 事業部を再稼働させる際は maru と並行になる
- **AnimaWorks サーバー**: launchd `com.animaworks.server` PID 99873 / port 18500 で稼働中
- **ai-research-hub への依存**: 毎朝6:00 launchd（`com.trinitydox.ai-research-hub`）が動く前提。停止すると rue が一次ソースを失う
- **fal_client / Pillow は miniforge python のみ**: Anima が Bash 経由で画像生成するときは `/opt/homebrew/Caskroom/miniforge/base/bin/python` を使う必要あり
- **承認済みが同 slot に残っていると queue backup**: 新規 pending が強制 pending 化される。古い approved を消してから新しいものを承認するルール
- **ハンドオフに機密情報を書かない**（auto-memory 既知）— 本ファイルにも API キー・トークン等は記載していない

## 変更ファイル一覧

### 新規作成

- `~/.animaworks/animas/cicchi/knowledge/topic_selection_criteria.md`（4層スコアリング選定基準）
- `~/.animaworks/tmp/x_image_20260506_evening_bg.png`（FLUX 背景）
- `~/.animaworks/tmp/x_image_20260506_evening.png`（オーバーレイ済み完成画像）
- `~/.animaworks/pending_posts/20260506T131722_evening.json`（業務AI 体制 第1号投稿）

### 編集

- `~/.animaworks/animas/cicchi/cron.md`（rue 委任プロンプトを ai-research-hub 参照フローに刷新）
- `~/.animaworks/animas/cicchi/injection.md`（参照ファイル一覧を再構成）
- `~/.animaworks/animas/cicchi/permissions.md`（リサーチディレクトリ Read 権限追加）
- `~/.animaworks/animas/cicchi/knowledge/agent-reach-tools.md`（ai-research-hub を一次ソースとして再構成）
- `~/.animaworks/animas/rue/injection.md`（委任受領時の必須参照ファイル4点を追加、Reddit/yt-dlp 削除）
- `~/.animaworks/animas/rue/permissions.md`（リサーチディレクトリ Read 権限追加）
- `.agent/units/x_unit.md`（業務AI 体制初投稿の記録・教訓追記）

### 削除

- `~/.animaworks/pending_posts/20260430T211122_morning.json`（旧体制パピヨン）
- `~/.animaworks/pending_posts/20260430T213350_evening.json`（旧体制パピヨン）

## サーバー状態

- launchd `com.animaworks.server` 稼働中（PID 99873）
- launchd `com.trinitydox.ai-research-hub` 稼働中（毎朝6:00、5ファイル出力）
- HTTP `http://localhost:18500` ヘルスチェック OK
- 稼働 Anima: maru / chiro / tama
- 停止 Anima: cicchi / kuro / rue / sora / hana

## Knowledge Lint レポート

knowledge_lint critical 0 / warning 0（53ファイルスキャン）。知識矛盾なし ✅
