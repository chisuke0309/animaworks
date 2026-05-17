---
unit: tiktok
updated: 2026-05-09
---

# TikTok事業部

## WHY（変わらない）

AI活用・生成AI・AIツール比較コンテンツをTikTokで発信。
フォロワー獲得 → TikTok Shop アフィリエイト収益化。

## 現在の戦略

- フォーマット: 5スライドカルーセル（9:16縦型）
- テーマ: AI活用 / 生成AI / AIツール比較 / AI業界ニュース
- 投稿頻度: 1日1本以上
- 最重要指標: 保存率・シェア数
- **CTA戦略**: コメント0連続中のため保存促進型を継続（feedback_insights.md の「データ駆動CTA転換ルール」）

## 現状

🟡 **maru / chiro / tama 稼働中（人間ゲート付き運用）**

### 運用モード（2026-05-09 確定）

**人間ゲート付き運用** — Anima は「制作 + Telegram 配信」までを担当。**chisuke の最終確認を経てから手動で TikTok に投稿する**。Anima から TikTok への自動投稿は行わない。

- ✅ Anima の責務: chiro 調査 → maru 委任 → tama 制作 → judge 採点 → freshness 確認 → Telegram 配信
- 🚫 chisuke の責務: Telegram で受領 → スマホで内容確認（事実関係・画像・キャプション）→ 違和感あれば差し戻し or スキップ → 問題なければ手動投稿

### この運用モードを取る理由（事故実績ベース）

5/9 一日で重大な事故が2件発生し、いずれも chisuke が直前で気づいて止めた:

1. **5/9朝枠**: 画像とJSONの乖離（？無しの古い画像で納品寸前）
2. **5/9夕方枠**: 事実誤認（「Claudeの記憶量が2倍」というハルシネーション）

両方とも自動投稿だったら **Anthropic Partner Network 申請中の信頼に直結する事故**。Anima の事実検証能力は現状「人間ゲート無しで投稿できるレベル」に達していない。

### 自動投稿に進む条件

以下が全て満たされたら、人間ゲートを段階的に外すことを検討:

- judge プロンプト改修（5/9実装）の効果が実 LLM テストで確認できる
- chiro の事実検証 protocol が実運用で 2週間以上同種事故ゼロ
- 06:30 自動スクレイピングが復旧
- chisuke の最終確認で差し戻し率が 10% 以下に安定する

## 次のアクション

- [ ] 5/9朝枠の修正版画像を chisuke スマホで TikTok 投稿（手動）
- [ ] 5/10朝枠 cron で **案E** が機能するか観察（maru 編集長プロトコル・委任テンプレ整理・tama セルフレビュー3項目）
- [ ] 5/10朝枠で tama がテーマ整合チェックを通過するか（製品名が overlay に登場するか）
- [ ] 5/10朝枠で maru の委任メッセージが軽くなっているか（手順書と重複していたルールが除かれているか）
- [ ] judge ルーブリック自体の質を観察（pass版でも「面白い・刺さる」コンテンツになっているかは別問題）
- [ ] 06:30 自動スクレイピングが Playwright sync/asyncio エラーで失敗 → 別途修正必要
- [ ] knowledge_lint.py の既存 critical 20件（tiktok_cookie_status / fal_key / x_post_approval 等）を別セッションで掃除

## Anima稼働状況

| Anima | ロール | 状態 |
|-------|--------|------|
| maru | TikTok Division Lead | 🟢 稼働中（品質チェック8項目化） |
| chiro | TikTokトレンド調査 | 🟢 稼働中 |
| tama | カルーセル制作 | 🟢 稼働中（差し戻し対応プロトコル追加） |

## メモ・教訓

- **5/9朝枠事故（JSON-画像乖離）**: judge は overlay_texts のテキスト文字列を採点するだけで、焼き済みPNGの中身を見ない。tama が JSON だけ修正して画像を再焼きせずに「修正完了」と報告 → judge pass → 古い画像で納品される構造的欠陥が発生。
- **解決策**: `tiktok_verify_image_freshness(draft_id)` を新設。JSONの`saved_at`と画像の mtime を比較、stale なら fail。maru/injection.md の品質チェック8番目に必須化。
- **5/9夕方枠事故（事実誤認）**: judge（Opus 4.7）自身が suggestion で「使える量」→「記憶量」と書き換えるハルシネーション。judge プロンプトに「事実主張保持原則」を追加 + `factual_claims`/`source_urls` パラメータ拡張で対策（ただし実 LLM テスト未実施）。
- **5/9夕方枠（Deep Research Max）**: judge 3回 fail → chisuke 判断で投稿中止。tama 性能問題の真因調査で **Sonnet 4.6 の能力不足ではなく、フロー設計の構造問題** と判明。案E（編集長プロトコル + 委任テンプレ整理 + tama セルフレビュー3項目）を実装。
- **lint辞書の漏れ**: tiktok 系ツール名の多くが `scripts/knowledge_lint.py` の `VALID_TOOL_NAMES` に未登録だった。今回まとめて追加済み。
- **画像焼き直し方法**: 既存PNGはオーバーレイ込みで上書きされているため、テキスト修正には FLUX で背景再生成が必要（コスト発生）。`tiktok_generate_carousel_images` ツールで自動化されている。
- **Role Contract 導入後の運用**: 5/6 から maru injection.md に Role/Specialty/Deliverables/Boundaries/DoD/Downstream/Escalation を追加。境界遵守・委任徹底は機能している。「指示外の正しい行動」（chiro への自発的事故共有）も観察された。
- **未承認ドラフト一括クリア（5/9 19:47）**: pending_approval 49件を一括で expired に更新。`_archive_20260509_expired/` にバックアップ保管。クリーンストートで 5/10 朝枠から再開。
