# HANDOFF - 2026-04-28

## 使用ツール
Claude Code

## 作業対象プロジェクト
AnimaWorks — Kyoka事業部 scenario_003 投稿準備

---

## 現在のタスクと進捗

### Kyoka事業部
- [ ] **Instagramアカウント @kisaragikyokaoffice を作成**（chisuke 本日対応予定）
- [ ] **scenario_003 を TikTok + Instagram に投稿**（chisuke 本日 18〜21時予定）
- [ ] 投稿後: Notion の scenario_003 を Posting Status=投稿済み・Posted At=投稿日に更新
- [ ] 投稿後: `video_inventory.md` の scenario_003 を「✅ 投稿済み」に更新
- [ ] rin/kiri/sumi を起動して scenario_002 のパッケージ生成を開始（第1投稿後）

### X事業部
- 前回から引き続き稼働中。特段変更なし。

---

## 試したこと・結果

- ✅ Notion から scenario_003 の TikTok/Instagram キャプション全文を取得・確認済み
- ✅ kyoka_scenario_003.mp4 の存在を確認（`~/.animaworks/common_knowledge/tiktok_templates/kyoka/assets/`）
- ℹ️ HeyGen Hyperframes（HTML→MP4）を検討 → **第1投稿後に評価**する方針で合意。今は投稿優先

---

## 次のセッションで最初にやること

1. **scenario_003 投稿確認**。投稿済みなら:
   - Notion の scenario_003: Posting Status=「投稿済み」・Posted At=投稿日
   - `~/.animaworks/animas/rin/knowledge/video_inventory.md` の scenario_003 を「✅ 投稿済み」に更新
2. **rin/kiri/sumi を起動**して scenario_002 のパッケージ生成を指示
   - `POST /api/animas/rin/chat` で起動通知（`{"message": "scenario_003の投稿完了。scenario_002のパッケージ生成を開始してください"}`）
3. Instagramアカウント作成済みなら Higgsfield Earn 登録に進む

---

## 注意点・ブロッカー

- **rin/kiri/sumiは第1投稿後に起動**（投稿前に起動すると在庫が未投稿のまま次を生成してしまう）
- **scenario_003 キャプション（コピペ用）は下記参照**

### TikTok キャプション
```
She walks where gods still linger.

古刹 — ancient ground, forgotten by time.

Follow @kisaragikyokaoffice ✨

#JapaneseMystery #KyokaAI #MysteriousJapan #AIBeauty
#AncientJapan #JapaneseAesthetic #AIGirl #EtherealBeauty
#SpiritualJapan #JapanVibes #AIAnimation #Kimono
#JapaneseGirl #DigitalArt #GenerativeAI
```

### Instagram キャプション
```
She walks where gods still linger.

古刹（kosan） — an ancient Buddhist temple, where moss reclaims the stones and shadows hold their breath.

This is 鏡花（Kyoka）. A figure from a Japan between memory and myth.

Follow @kisaragikyokaoffice ✨

#JapaneseMystery #KyokaAI #MysteriousJapan #AIBeauty #AncientJapan #JapaneseAesthetic #AIGirl #EtherealBeauty #SpiritualJapan #JapanVibes #AIAnimation #Kimono #JapaneseGirl #DigitalArt #GenerativeAI #AICharacter #MysteriousGirl #JapanMystery #AsianBeauty #AIArt #FantasyAI #JapaneseWoman #AnimeAesthetic
```

---

## 関連ファイル

| ファイル | 内容 |
|---------|------|
| `.agent/units/kyoka_unit.md` | Kyoka事業部の戦略・在庫・次のアクション |
| `~/.animaworks/animas/rin/knowledge/video_inventory.md` | 動画在庫・投稿順序・投稿済み状態 |
| `~/.animaworks/animas/rin/knowledge/notion_schema.md` | Notion DBスキーマ・ページID一覧 |
| `~/.animaworks/animas/sumi/knowledge/posting_log.md` | キャプション重複防止ログ |
| `~/.animaworks/common_knowledge/tiktok_templates/kyoka/assets/` | 動画素材（scenario_001〜003） |
| Notion DB | https://www.notion.so/f1d407fcb3d94ca78cd81ddbe2c11d67 |
