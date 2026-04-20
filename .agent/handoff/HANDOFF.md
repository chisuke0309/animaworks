# HANDOFF — 2026-04-19 午前

## 使用ツール
Claude Code (Sonnet 4.6)

---

## 作業対象プロジェクト
AnimaWorks — yomi（CrowdWorks案件巡回）の絞り込みフィルタ強化

---

## 今回セッションで実施したこと

### 1. yomi昨夜巡回結果の確認

- 04-18 20:03 実行：28件ヒット → 24件Notion登録（4件は400エラースキップ）
- スコア分布: ★★★3件 / ★★11件 / ★9件 / 除外1件
- 問題: コンサル以外（SNS/EC/エンジニア/建築/マーケ系）が多数混入

### 2. `core/tools/crowdworks.py` キーワード除外強化

**変更内容**

| 追加 | 内容 |
|------|------|
| `_EXCLUDE_KEYWORDS` | Instagram / インスタグラム / Amazon / 楽天 / TikTok Shop |
| `_TITLE_EXCLUDE_KEYWORDS`（新設） | エンジニア / デベロッパー / データサイエンティスト / 機械学習 / ライター / ライティング / 建築 / CAD / 施工 / SNSマーケ / SNS運用 / マーケター / マーケティング / インサイドセールス / セールス / セキュリティ |
| `score_job` ロジック | タイトル限定除外チェック（`title_excluded_by`）を追加 |

**効果**: Notion登録候補 22件 → 6件

### 3. `yomi/procedures/crowdworks-pmo-workflow.md` 更新

- フェーズ3に `score >= 40` フィルタ追加（★以下はNotion登録しない）
- おすすめ度判定レベルの説明を更新

### 4. コミット済み

```
7c6d554d  fix(crowdworks): PM/PMO案件に特化した除外キーワード強化
```

---

## Notion登録される案件（今夜から適用）

| スコア | 案件 |
|-------|------|
| ★★★ 74 | AI活用・業務自動化アドバイザー（Claude Codeレクチャー） |
| ★★★ 66 | PMO 企業内AI導入推進案件（応募1件・固定30万） |
| ★★★ 65 | 観光DX事業 伴走型CS（時給1,500〜1,700円） |
| ★★ 54 | プロジェクトサポート・営業推進メンバー |
| ★★ 49 | AI業務ディレクター |
| ★★ 47 | PM別荘事業推進 |

---

## Anima稼働状況

| anima | enabled | ロール |
|-------|---------|--------|
| cicchi / rue / kuro / sora / hana | false | 元X事業部・停止中 |
| maru | true | TikTok事業部リーダー |
| chiro | true | TikTokトレンド調査 |
| tama | true | TikTokカルーセル制作 |
| yomi | true | CrowdWorks PM/PMO案件巡回（毎日20:03） |
| rin / kiri / sumi | false | Kyoka事業部（素材プール完成後に再稼働） |

---

## 次のセッションで最初にやること

1. **★★★案件への応募判断** — 特にPMO AI導入案件（応募1人・固定30万）と AI活用アドバイザー（時給4,000円）を優先検討。Notionの「応募する」チェックを入れればyomiが応募文生成
2. **fork remoteへのpush確認** — 今回の変更（`7c6d554d`）を `fork` remote へ push するか確認
3. **maruチーム改善方向性** — 「カルーセル形式に限界」の次の方向性をユーザーから聞く
4. **Kyoka素材バリエーション量産** — reveal/closeup/gesture 各5〜10件

---

## 注意点・ブロッカー

- **Notionカテゴリ選択肢**: 昨夜4件が400エラーでスキップ。新カテゴリ（PM/PMO等）がNotionのDBに存在しない可能性あり → 次回巡回後にエラーログ確認
- **maruチームの改善提案はユーザーから先に聞く** — AIから先回りして提案しない
- **TikTok Cookie期限**: 次回 2026-10-14頃
- **Kling v2.5 Turbo Proコスト**: 5秒あたり約$1.75（Kyoka素材量産時は予算管理）
