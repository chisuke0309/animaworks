# Notion DB Guide — Kyoka素材管理用データベース

素材生成のプロンプト設計・進捗管理をNotionで行うためのガイド。
ローカルの `asset_pool.json` との役割分担も含む。

---

## Notion DB vs asset_pool.json

| | Notion DB | asset_pool.json |
|--|-----------|-----------------|
| **役割** | 人間の作業管理・進捗追跡 | Animaの参照・自動処理用 |
| **誰が更新** | 人間（素材生成時） | Anima（投稿時に使用カウント更新） |
| **アクセス** | ブラウザ・iPad | ローカルファイル |
| **主用途** | プロンプト設計・作業進捗 | 素材選択・使用履歴 |
| **同期** | Notion → asset_pool.json（一方向） | - |

**ルール**: 新規素材はまずNotionに登録。生成完了後にasset_pool.jsonへ同期。

---

## DB設計: `Kyoka Asset Prompts`

### プロパティ

| プロパティ名 | 型 | 用途 | 必須 |
|-----------|-----|------|------|
| **ID** | Title | `kyoka_closeup_001` 形式 | ✅ |
| **Scene Type** | Select | closeup / reveal / atmosphere / disappear / gesture / pov | ✅ |
| **Variant** | Number | シーン種別ごとの連番 | ✅ |
| **FLUX Prompt** | Rich Text | 画像生成プロンプト | ✅ |
| **Kling Prompt** | Rich Text | 動画生成プロンプト | ✅ |
| **Status** | Select | 未着手 / 画像済 / 動画済 / 承認 / 却下 | ✅ |
| **Image URL** | URL | fal.ai生成画像のURL（一時） | — |
| **Local Image** | Files & Media | ダウンロード済み画像 | — |
| **Local Video** | Files & Media | ダウンロード済み動画 | — |
| **Duration (sec)** | Number | 5 or 10 | — |
| **Season** | Select | late_spring / early_summer / midsummer / autumn / winter / early_spring | — |
| **Tags** | Multi-select | mysterious / dramatic / hand_gesture / static 等 | — |
| **Notes** | Rich Text | 品質メモ・改善点 | — |
| **Created** | Created Time | 自動 | ✅ |
| **Updated** | Last Edited Time | 自動 | ✅ |

### Statusの遷移

```
未着手 → 画像済 → 動画済 → 承認 / 却下
                          ↓
                    （却下時は削除 or 再生成）
```

---

## 初期セットアップ手順

1. Notionで新規DBを作成: `Kyoka Asset Prompts`
2. 上記プロパティを設定
3. Viewを3つ作成:
   - **Board View**: Status別のカンバン表示
   - **Table View**: 全素材のスプレッドシート表示
   - **Gallery View**: Local Imageでサムネイル表示
4. Filter: Status = 「未着手」のみ表示するビューを作成（作業用）

---

## 初期投入: 80行のプロンプトバリエーション

### 投入ルール

- 4シーン × 20バリエーション = 80行
- シーン別配分（asset-pool-management.mdと一致）:
  - closeup: 20
  - reveal: 10
  - atmosphere: 15
  - disappear: 10
  - gesture: 15
  - pov: 10

### プロンプト量産の流れ

1. Claude等でシーン別のプロンプトバリエーションを生成させる
2. 各バリエーションに `variant` 番号を付与
3. Notionに手動 or API経由で投入
4. Status = 「未着手」で登録

---

## 日次作業フロー（素材生成時）

1. **Notionを開く** → Status=「未着手」ビュー
2. **1行選ぶ** → FLUX Promptをコピー
3. **fal.ai Web UIで画像生成**
4. **画像URLをNotionに貼り、Statusを「画像済」に**
5. **Kling Promptをコピー、画像URLと一緒にKlingに投入**
6. **動画生成** → ダウンロード
7. **ローカル保存**（命名規則に従ってリネーム）
8. **Notionに画像・動画をアップロード、Statusを「承認」に**
9. **asset_pool.jsonに同期**

---

## asset_pool.jsonへの同期

手動同期 or スクリプト自動化。

### 手動同期の場合

Notionの「承認」ステータスの行を見て、asset_pool.jsonに以下形式で追加:

```json
{
  "id": "kyoka_closeup_001",
  "scene_type": "closeup",
  "variant": 1,
  "flux_prompt": "...",
  "kling_prompt": "...",
  "image_path": "assets/kyoka_closeup_001_start.jpg",
  "video_path": "assets/kyoka_closeup_001.mp4",
  "duration_sec": 5,
  "status": "approved",
  "used_count": 0,
  "last_used": null,
  "tags": ["static", "zoom_out", "cherry_blossom", "late_spring"],
  "created_at": "2026-04-17T09:00:00+09:00"
}
```

### 自動同期（将来）

`notion-to-asset-pool.py` スクリプトを作って、Notion APIから承認済みレコードを取得し、asset_pool.jsonに反映。sumiの日次処理前に実行する仕組みが理想。

---

## タグの標準化

Notionの「Tags」Multi-selectで以下を用意:

### 動きタグ
- `static`
- `slow_motion`
- `hand_gesture`
- `head_turn`
- `camera_pull`
- `zoom_out`

### 構図タグ
- `close_up`
- `wide_shot`
- `back_view`
- `profile`
- `full_body`

### 雰囲気タグ
- `mysterious`
- `dramatic`
- `serene`
- `tense`
- `melancholic`

### 要素タグ
- `cherry_blossom`
- `lantern`
- `fog`
- `moonlight`
- `kimono_sleeve`
- `hair_wind`

---

## 権限・共有

- 個人運用で良い（チーム共有は不要）
- スマホ・iPadからも編集可能にする（Notionアプリ）
- スクリーンショット共有を避ける場合はAPI経由でのみ同期

---

## メンテナンス

### 月次レビュー

- 使用頻度の低い素材を削除候補に
- 「承認」だが `used_count > 10` の素材を新規生成で置き換え検討
- 季節が変わったら旧季節の素材をアーカイブ

### 品質管理

- 「却下」になった素材のプロンプトを分析
- 失敗パターンは `motion-patterns.md` に追記
- 成功パターンは標準化してSkillに反映
