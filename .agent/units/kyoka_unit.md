---
unit: kyoka
updated: 2026-04-28
---

# Kyoka事業部

## WHY（変わらない）

AIキャラクター「鏡花（Kyoka）」の動画をTikTokに投稿し、**収益化**する。
- チャネル: TikTok Shop アフィリエイト / Higgsfield Earn（AI動画→Instagram報酬）
- 3ヶ月後目標: 月5万円収益、TikTokフォロワー10,000人
- アカウント: @kisaragikyokaoffice

## アカウント

- Google: macOS キーチェーン参照（Kyoka事業部専用アカウント・2026-04-28作成）
- TikTok: @kyokakisaragi（2026-04-28作成・scenario_003投稿済み）
- Instagram: @kyokakisaragi.ai（2026-04-28作成・scenario_003投稿済み・`.ai`はAI明示と空き優先）

> パスワード・メアド本体はキーチェーン管理。ファイルには記載しない。

### Bio（TikTok / Instagram 共通）

```
鏡花 — Kyoka
She walks where gods still linger.
🎋 Kyoka — Japanese mystery × AI
```

## キャラクター

| キャラ | 役割 | 状態 |
|--------|------|------|
| 鏡花（Kyoka） | 姉・ミステリアス・フック担当 | 動画制作済み |
| 小春（Koharu） | 妹・日常系・共感担当 | 未実装 |

## 現在の戦略（2026-04-25 確定）

### ポジション

**「ミステリアスな日本人女性」× 海外向け英語キャプション**
- 競合の多い美女動画ドメインで差別化するため、海外受けするJapanイメージ（古刹・竹林・路地）に特化
- TikTok + Instagram（Higgsfield Earn）の2チャネル並走で収益化を早める

### フェーズ1：世界観確立（〜5月末）

**投稿順序（インパクト降順）**:

| 順番 | ファイル | テーマ | 投稿予定 |
|------|----------|--------|---------|
| 1本目 | kyoka_scenario_003 | 青もみじの古刹 | 最初に出す（最強のJapan印象） |
| 2本目 | kyoka_scenario_002 | 竹林の雨上がり | 1週後 |
| 3本目 | kyoka_scenario_001 | 青葉の路地 | 2週後（柔らかく着地） |

**投稿頻度**: 週1〜2本  
**投稿タイミング**: 日本時間18〜21時（海外西海岸朝・欧州夕方）

**英語キャプション構造**:
```
She appears where the old stones remember.

🎋 Japanese mystery | AI beauty | @kisaragikyokaoffice

#JapaneseMystery #KyokaAI #MysteriousJapan #AIBeauty
#AncientJapan #Kimono #JapaneseAesthetic #AIGirl
```

### 旧素材の扱い

`closeup_001 / gesture_001 / gesture_003 / reveal_001`（音楽なし・5秒）はアーカイブ。公開しない。将来BGM後付けが確立したら再評価。

### 収益化：Higgsfield Earn（並走）

- 同じ動画をInstagram Reelsにクロスポスト
- @kisaragikyokaoffice のInstagramアカウントを作成する必要あり（未着手）
- 月間1000〜5000再生で報酬発生ライン（確認要）

## パイプライン

**パイプライン（新・採用）**: GPT Image 2.0（6フレーム絵コンテ）→ Seedance 2.0（15秒動画・BGM付き）

- 1シナリオ = 15秒・6フレーム・Seedance BGM自動付与
- コスト: 90コイン/本、月1000コイン（≒11本/月）、年間プラン加入済み（3万円）
- Seedanceの癖: 冒頭に静止画が混入 → 後加工でトリム前提

**パイプライン（旧・アーカイブ）**: FLUX + LoRA → Kling動画（音楽なし5秒クリップ）

## 素材在庫

| 種別 | 本数 | 内容 | 使用方針 |
|------|------|------|---------|
| 音楽付き15秒（新） | 3本 | 001「青葉の路地」/ 002「竹林の雨上がり」/ 003「青もみじの古刹」| ✅ 投稿する |
| 音楽なし（旧） | 4本 | closeup_001 / gesture_001 / gesture_003 / reveal_001 | 🗄️ アーカイブ |

素材保存先: `~/.animaworks/common_knowledge/tiktok_templates/kyoka/assets/`

**Notion DB**: https://www.notion.so/f1d407fcb3d94ca78cd81ddbe2c11d67
- スキーマ詳細・ページID: `~/.animaworks/animas/rin/knowledge/notion_schema.md`
- 投稿管理プロパティ（2026-04-25追加）: Posting Order / Posting Status / Posted At / TikTok Caption / Instagram Caption

## 次のアクション（最大3件）

- [ ] **Instagramアカウント @kisaragikyokaoffice を作成**（2026-04-28 本日対応予定）
- [ ] **scenario_003 を TikTok + Instagram に投稿**（2026-04-28 本日対応予定・18〜21時推奨）→ 投稿後にNotionとvideo_inventory.mdを更新
- [ ] 追加シナリオ企画（夏祭り・朝靄・紅葉前夜・雪景色）でフェーズ2素材を確保

## Anima稼働状況

| Anima | ロール | 状態 |
|-------|--------|------|
| rin | 事業部リーダー・企画・品質管理 | 🟡 設定済み・第1投稿後に稼働 |
| kiri | リサーチャー・海外ハッシュタグ調査 | 🟡 設定済み・第1投稿後に稼働 |
| sumi | 投稿パッケージ生成（キャプション・ハッシュタグ） | 🟡 設定済み・第1投稿後に稼働 |

## メモ・教訓

- fal.ai経由Seedanceは肖像権フィルタで拒否される → 本家Seedanceを使う
- GPT Image 2.0は放置すると仕様書で返答する → 「MANDATORY IMAGE GENERATION MODE」を冒頭・末尾に必須
- Notionスキーマ変更は `notion-update-data-source` ツール（ADD COLUMN DDL）で可能。DB作り直し不要
- HeyGen Hyperframes（HTML→MP4）は将来的にキャプションアニメ焼き込みに使える候補。第1投稿後に評価する
