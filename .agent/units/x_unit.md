---
unit: x
updated: 2026-05-06
status: 業務AI体制（手動運用テスト中・Anima停止）
---

# X事業部

## 🚀 2026-05-06 業務AI 体制での初投稿準備完了（手動）

**当日17:00 evening 枠発射予定**: GitLab AIパラドックスをテーマにした業務AI 体制での **第1号投稿** を chisuke 手動経由で pending 保存・承認済み。

- ID: `20260506T131722_evening`
- status: **approved**
- 品質スコア: 9.3/10（hook 8 / その他は10満点）
- 画像: `~/.animaworks/tmp/x_image_20260506_evening.png`（Pillow で日本語タイトル「週7時間が消えている。/ GitLabが指摘するAIパラドックス」をオーバーレイ済み）
- 発射: cron `0 17 * * *` で `x_post_execute_pending slot=evening`

`status.json.enabled` は **5体すべて false のまま**（cicchi 事業部 Anima は止まっており、chisuke 手動 + 私の代行で投稿準備した）。

## 🔄 2026-05-06 ジャンル転換 完了

**判断**: 旧体制（ペット・グルーミング情報、6週間でフォロワー9名）を完全終了し、屋号 trinitydox と整合する **業務AI / AI活用 / 業務改善** ジャンルへ全面転換。
あわせて NEXUS スタイルの **Role Contract 構造**（先日 maru で導入したもの）を cicchi 事業部 5 体に展開。
さらに既存リポジトリ `~/Projects/ai-research-hub/`（毎朝6:48に Obsidian Vault に5ソースを保存）を rue の一次ソースに位置付け、`topic_selection_criteria.md`（4層スコアリング）で投稿ネタ選定の透明性を確保。

---

## 現在の戦略（業務AI 体制）

### ターゲット
PM / DX推進担当 / 経営層 / 事業部長 / コンサルタント / SaaS担当

### 投稿ジャンル A〜E

| 記号 | ジャンル | 想定頻度 |
|------|---------|---------|
| A | 業務改善ケーススタディ | 週1〜2 |
| B | AIツール実務レビュー（Claude / Gemini / NotebookLM 等） | 週1 |
| C | PM × AI 実務（chisuke 本業ネタ・抽象化必須） | 週1〜2 |
| D | AI業界ニュースの実務翻訳 | 週2〜3 |
| E | プロンプト/Skill 公開 | 隔週〜月1 |

### 禁止テーマ（5項目を全 anima Boundaries に明示）
- AI副業・稼ぎ方系
- ペット・健康情報（旧体制の残骸）
- クライアント固有情報（抽象化レベル: 「ある製造業のデータ分析PJで…」まで）
- Anthropic Partner Network 公式発表（指示があるまで）
- AGI / シンギュラリティ煽り系

### 収益動線
trinitydox サイト誘導 → PMO/DX 案件相談（KPIに「サイト誘導数」を新設）

---

## KPI（業務AI 体制で再校正）

| 指標 | 現在 | 1ヶ月後 | 2ヶ月後 | 3ヶ月後 |
|------|------|---------|---------|--------|
| Xフォロワー数 | 9 | 50 | 200 | 500 |
| エンゲージメント率 | - | 2% | 3% | 3%以上 |
| trinitydox サイト誘導数（週次） | 0 | 5 | 20 | 50 |

---

## Anima稼働状況

| Anima | ロール | 状態 |
|-------|--------|------|
| cicchi | X Division Lead（オーケストレーター） | ⛔ 停止（Role Contract導入済み） |
| rue | X Division Researcher | ⛔ 停止（Role Contract導入済み） |
| kuro | X Division Copywriter | ⛔ 停止（Role Contract導入済み） |
| sora | X Division Visual Director | ⛔ 停止（Role Contract導入済み・犬種イラストフロー削除済み） |
| hana | X Division Engagement Officer | ⛔ 停止（Role Contract導入済み） |

---

## 次のアクション

1. **本日17:00 の発射結果を確認**: `~/.animaworks/pending_posts/20260506T131722_evening.json` の status が `posted` になり、tweet_id が記録されているか
2. **22:00 のエンゲージメント計測結果を確認**: impressions / likes / RTs が `x_post_log.md` に追記されるはず（cicchi 停止中のため手動で見にいく）
3. **chisuke 手動（任意）**:
   - X プロフィール文の業務AI 用への書き換え（既に完了との報告あり）
   - 固定ツイートの差し替え
   - cicchi 事業部 5 体の `enabled: true` 切替（運用再開判断時）
4. **次回以降**:
   - rue が `cicchi/knowledge/competitor_accounts.md` を埋める（業務AI / DX 系発信アカウント発掘）
   - 朝夕2枠を Anima 駆動で自動運用

---

## メモ・教訓

- **記憶クリーンアップは必須だった**: ジャンル転換時に knowledge ファイルを消すだけでは不足。`episodes/`・`vectordb/`・`activity_log/`・`state/conversation.json` が search_memory のソースになっており、過去のペット文脈が逆流するリスクがあった。MEMORY.md「全Animaクリーンアップ手順」を実施して解消。
- **Role Contract は cicchi 事業部全員に展開して問題なかった**: maru で実証済みの構造を5体すべてにコピー&カスタマイズ。knowledge_lint critical 0 / warning 0 で完了。
- **削除した knowledge は 約100本**: ペット運用記録（niche*.md、archive/、週次戦略履歴等）。フレームワーク部分は `genre_map.md` `weekly_strategy.md` に再構築。
- **保持した技術記録**: `image_posting_workflow.md`（OAuth1 認証バグ修正）、`x_account_suspension.md`（凍結対応）、`x_api_credential_fix.md`（API認証）— インフラノウハウは業務AI 体制でも有用。
- **ai-research-hub を一次ソースに位置付け**: 既存リポジトリ `~/Projects/ai-research-hub/`（毎朝6:00 launchd・6:48に5ソースを Obsidian Vault に保存）を rue の最優先情報源にした。ハルシネーション抑制 + ゼロから検索する負荷軽減。
- **使えなかった調査ツール**: yt-dlp（YouTube 署名チャレンジ未対応で 429）と Reddit JSON（403 Blocked）は injection から削除。bird CLI / Exa / Jina Reader / mcporter / web_search は完全動作確認済み。
- **投稿ネタ選定基準を明文化**: `topic_selection_criteria.md` に4層スコアリング（必須フィルター → 5軸×5点 → ジャンル偏り回避 → 最終判断）。15点以上で投稿候補。なぜそのネタを選んだかが報告に必ず残る。
- **画像へのテキストオーバーレイは2段階が定石**: FLUX に日本語を直接書かせると文字化け確実。FLUX で背景生成 → Pillow で日本語オーバーレイ（半透明黒の暗幕＋白文字）が綺麗に出る。`/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc` 使用。
- **fal_client は miniforge 環境にしか入っていない**: `.venv/bin/python` ではなく `/opt/homebrew/Caskroom/miniforge/base/bin/python` で実行する必要あり（venv は miniforge へのシンボリックリンクだが site-packages を共有していない様子）。
- **承認 API は `/api/approvals/posts/{id}/approve`**: prefix が `/api` なので `/approvals/...` だと 405。openapi.json で確認可能。
- **save_pending は同 slot に approved が残っていると新規を強制 pending 化**: queue backup 防止の安全装置。古い approved を削除してから新規を承認すれば良い。今回は旧体制（ペット）の `20260430T213350_evening` `20260430T211122_morning` を削除。

---

## 旧体制の参考記録（ペット・グルーミング 2026-03 〜 2026-05-02）

- 稼働期間: 約6週間
- 最終フォロワー: 9名
- 技術的教訓:
  - X API 401 の真因: `x_post_log.md` の `—`（全角ダッシュ）vs `"-"` ミスマッチ（commit: 1a0e7245）
  - pending queue 詰まり: 同slot に approved が既にある場合の処理（commit: adad38f2）
  - フォロワー増加の壁: 短文・感情フック・画像添付施策を試したが伸びず → ジャンル自体の問題と判断
