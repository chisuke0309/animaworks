# Asset Pool Management — 素材の命名・保存・インデックス

生成した素材（静止画・動画）をローカルに保存し、sumi（または人間）が参照できる形で管理する。

---

## 保存先ディレクトリ

```
~/.animaworks/common_knowledge/tiktok_templates/kyoka/assets/
```

このディレクトリ配下に全素材を保存する。

---

## ファイル命名規則

### 形式

```
kyoka_{シーン種別}_{連番3桁}_{用途}.{拡張子}
```

### シーン種別（現状定義）

| 種別 | 内容 | 元の型 |
|------|------|--------|
| `closeup` | アップ顔・ズームアウト系 | kyoka_mysterious_reveal Scene 3系 |
| `reveal` | 登場・正面向き系 | kyoka_mysterious_reveal Scene 2系 |
| `atmosphere` | 背景・雰囲気カット | kyoka_mysterious_reveal Scene 1系 |
| `disappear` | 消失・退場系 | kyoka_mysterious_reveal Scene 4系 |
| `gesture` | 所作・手の動き系 | NEW（#002で追加） |
| `pov` | 一人称視点系 | kyoka_pov_encounter型 |

### 用途サフィックス

| サフィックス | 内容 |
|------------|------|
| `_start.jpg` | FLUX生成画像（動画の開始フレーム・fal.aiはJPG出力） |
| `_end.jpg` | 動画最終フレーム（参考・選択用） |
| `.mp4` | 動画本体（サフィックスなし） |

### 命名例

```
kyoka_closeup_001_start.jpg    — 1本目のクローズアップ用FLUX画像
kyoka_closeup_001_end.jpg      — 同じ動画の最終フレーム
kyoka_closeup_001.mp4          — 動画本体
kyoka_gesture_001_start.jpg    — 1本目の所作系FLUX画像
kyoka_gesture_001.mp4          — 所作系動画本体
```

---

## asset_pool.json スキーマ

**配置**: `~/.animaworks/common_knowledge/tiktok_templates/kyoka/asset_pool.json`

```json
{
  "version": 1,
  "updated_at": "2026-04-17T09:00:00+09:00",
  "assets": [
    {
      "id": "kyoka_closeup_001",
      "scene_type": "closeup",
      "variant": 1,
      "flux_prompt": "kyoka, close-up portrait, ...",
      "kling_prompt": "A beautiful woman in a traditional black kimono standing completely still...",
      "image_path": "assets/kyoka_closeup_001_start.jpg",
      "video_path": "assets/kyoka_closeup_001.mp4",
      "duration_sec": 5,
      "status": "approved",
      "used_count": 0,
      "last_used": null,
      "tags": ["static", "zoom_out", "cherry_blossom", "late_spring"],
      "notes": "カメラズームアウト＋花びら舞う。顔一貫性◎",
      "created_at": "2026-04-17T09:00:00+09:00"
    }
  ]
}
```

### フィールド定義

| フィールド | 型 | 必須 | 説明 |
|----------|-----|------|------|
| `id` | string | ✅ | ファイル名と一致（拡張子なし） |
| `scene_type` | string | ✅ | closeup / reveal / atmosphere / disappear / gesture / pov |
| `variant` | number | ✅ | シーン種別ごとの連番 |
| `flux_prompt` | string | ✅ | 静止画生成プロンプト |
| `kling_prompt` | string | ✅ | 動画生成プロンプト |
| `image_path` | string | ✅ | 相対パス（FLUX画像） |
| `video_path` | string | ✅ | 相対パス（動画） |
| `duration_sec` | number | ✅ | 動画秒数（5 or 10） |
| `status` | enum | ✅ | `pending` / `approved` / `rejected` |
| `used_count` | number | ✅ | 投稿での使用回数（sumiが更新） |
| `last_used` | string \| null | ✅ | 最後に使った日時 ISO 8601 |
| `tags` | string[] | — | 検索・フィルタ用タグ |
| `notes` | string | — | 品質メモ |
| `created_at` | string | ✅ | 生成日時 ISO 8601 |

---

## 素材の使い回し戦略

sumiが日次で素材を選ぶときのロジック：

```
1. scene_type別にassetsをフィルタ
2. status == "approved" のみ対象
3. used_count が最小のものを優先
4. 同率なら last_used が古いものを優先
5. タグで季節・雰囲気をマッチ
6. 選択したassetの used_count を+1、last_used を更新
```

---

## タグ運用ルール

タグは素材の特徴を表すキーワード。sumiが適切に使い分けるために重要。

### 推奨タグ分類

| カテゴリ | タグ例 |
|---------|--------|
| **動き** | `static`, `slow_motion`, `hand_gesture`, `camera_pull` |
| **構図** | `close_up`, `wide_shot`, `back_view`, `profile` |
| **雰囲気** | `mysterious`, `dramatic`, `serene`, `tense` |
| **季節** | `late_spring`, `summer`, `autumn`, `winter` |
| **要素** | `cherry_blossom`, `lantern`, `fog`, `moonlight` |
| **シーン種別** | `reveal`, `closeup`, `disappear` 等 |

---

## 目標保有数

| シーン種別 | 目標バリエーション数 |
|----------|---------------------|
| closeup | 20 |
| reveal | 10（振り返りNGのため少なめ） |
| atmosphere | 15 |
| disappear | 10 |
| gesture | 15 |
| pov | 10 |
| **合計** | **80** |

この数があれば、同じ素材の使い回しを最小限に抑えつつ、20〜30日分の投稿を回せる。

---

## 管理フロー

1. fal.ai Web UIで素材を生成
2. ローカルにダウンロード
3. 命名規則に従ってリネーム
4. `assets/` ディレクトリに保存
5. `asset_pool.json` にエントリ追加
6. Notion DBのステータスを更新

---

## バックアップ

fal.aiのCDN URLは期限切れの可能性がある。
**ローカル保存を必ず行う**こと。LoRA URLが切れた場合に備えて `.safetensors` ファイルもバックアップ推奨。
