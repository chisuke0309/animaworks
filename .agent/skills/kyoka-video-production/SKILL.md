---
name: kyoka-video-production
description: >
  AIキャラクター「鏡花（Kyoka）」のTikTok動画素材を fal.ai Web UIで
  手動生成するための手順とノウハウ。FLUX+LoRAで画像を生成し、
  Kling v2.5 Turbo Pro で動画化する2段パイプライン。
  「Kyoka」「鏡花」「TikTok動画」「fal.ai」「LoRA」「動画素材生成」等の作業で使用。
metadata:
  model: sonnet
risk: low
source: trinitydox
---

## このスキルを使う場面

- 鏡花のTikTok動画素材を手動生成するとき
- 素材プールに新しいバリエーションを追加するとき
- プロンプト設計で迷ったとき（→`prompt-engineering-guide.md`）
- 過去の成功パターンを参照したいとき（→`motion-patterns.md`）

---

## パイプライン全体

```
【素材生成（人間・fal.ai Web UI）】
Step 1: FLUX + LoRA → 静止画（576×1024, 9:16）
             ↓
Step 2: Kling v2.5 Turbo Pro i2v → 動画（5秒 or 10秒）
             ↓
Step 3: ローカル保存（asset_pool.jsonに登録）

【日次投稿（Anima自動・別スキル）】
テロップ合成 → BGM → TikTok投稿
```

---

## Step 1: FLUX画像生成

**エンドポイント**: `fal-ai/flux-lora`

**標準JSONテンプレート:**

```json
{
  "prompt": "kyoka, [シーンごとの指示], piercing intense gaze, fierce mysterious expression, traditional Japanese kimono, obi sash, black kimono with gold peony embroidery, cherry blossom petals falling around her, pink petals in air, late spring night, ultra-realistic, photographic, 8K",
  "loras": [
    {
      "path": "https://v3b.fal.media/files/b/0a966fb0/hxvTK_oyDRAWRd_JLOMQH_pytorch_lora_weights.safetensors",
      "scale": 1.5
    }
  ],
  "image_size": { "width": 576, "height": 1024 },
  "num_inference_steps": 28,
  "guidance_scale": 3.5,
  "num_images": 1
}
```

**⚠️ FLUXは `negative_prompt` を受け付けません。** positive prompt と guidance_scale だけで制御します。避けたい要素は「これを出すな」ではなく「これを出せ」の形で書き直すこと。

例:
- ❌ `negative: western dress` → ✅ positive に `traditional Japanese kimono, obi sash` を明示
- ❌ `negative: smiling` → ✅ positive に `fierce mysterious expression, no smile` を入れる

**変更厳禁パラメータ:**
- `loras[0].scale`: **1.5固定**
- `image_size`: **576×1024固定**（9:16縦型）
- `num_inference_steps`: 28
- `guidance_scale`: 3.5

**差し替え箇所:**
- `prompt` の `[シーンごとの指示]` 部分のみ
- 必要に応じて季節要素（`cherry blossom` など）

---

## Step 2: Kling動画化

**エンドポイント**: `fal-ai/kling-video/v2.5-turbo/pro/image-to-video`

### フィールド一覧（公式Schema）

| フィールド | 型 | 必須 | 用途 |
|-----------|-----|------|------|
| `prompt` | string | ✅ | 動きの指示 |
| `image_url` | string | ✅ | 開始画像のURL |
| `tail_image_url` | string | - | **終了画像のURL（大回転・大きな動きに必須）** |
| `duration` | `"5"` or `"10"` | - | 秒数（文字列） |
| `negative_prompt` | string | - | 避けたい要素 |
| `cfg_scale` | float | - | プロンプト追従度（デフォルト0.5） |

※`aspect_ratio` フィールドは**無い**。開始画像から自動継承。

---

### パターンA: 単一画像（静止・微動のみ）

```json
{
  "prompt": "[動きの指示]. Fixed camera, no zoom, no pan.",
  "image_url": "{{開始画像のURL}}",
  "duration": "5",
  "negative_prompt": "blur, distort, low quality, face change, inconsistent features, camera zoom, camera pan, camera movement, dolly",
  "cfg_scale": 0.9
}
```

**用途**: 静止＋微動・軽いカメラワーク

---

### パターンB: 2枚指定（大回転・大きな動き）★推奨

```json
{
  "prompt": "[動きの指示（2枚の間の動きを説明）]",
  "image_url": "{{開始画像のURL}}",
  "tail_image_url": "{{終了画像のURL}}",
  "duration": "5",
  "negative_prompt": "abrupt motion, teleport, face morph, distorted face, blurry face, flickering",
  "cfg_scale": 0.7
}
```

**用途**: 
- 後ろ姿→正面の振り返り
- プロフィール→フロントの回転
- 遠→近の寄り
- その他、単一画像では顔崩れしがちな動き

**重要**:
- 両方の画像を**FLUX + 同じLoRA**で生成すれば、両端の顔一貫性が確定する
- Klingは2枚の間を**補間**するので、背景・花びらの位置差異は自然に吸収される
- `seed` 固定は不要（むしろ無い方が動きが自然）
- `cfg_scale` は0.7程度（2枚の制約があるので高くしすぎない）

---

## コスト見積もり

| Step | 単価 | 1クリップ |
|------|------|----------|
| FLUX画像 | — | ~$0.03 |
| Kling v2.5 Turbo Pro i2v (5秒) | ~$0.35/秒 | ~$1.75 |
| **合計（5秒動画1本）** | | **~$1.78** |

※Wan 2.2（$0.10/秒）は品質不足だったためKlingを採用。

---

## 作業フロー

1. **Notion DBで次に作る素材を選択**（→`notion-db-guide.md`）
2. **FLUXプロンプトを調整してfal.ai Web UIで画像生成**
3. 画像の品質確認（顔の一貫性・着物の正確さ）
   - NGなら `num_inference_steps` を30に上げて再生成
4. **画像URLを控えて、Klingに投入**
5. Klingプロンプトも調整（動きの指示）
6. 動画の品質確認（→`motion-patterns.md`）
7. ローカルに保存（→`asset-pool-management.md`）
8. NotionでステータスをUpdate

---

## 関連ファイル

- `prompt-engineering-guide.md` — プロンプト設計の知見
- `motion-patterns.md` — 成功／失敗パターンカタログ
- `asset-pool-management.md` — ローカル素材の命名規則と保存先
- `notion-db-guide.md` — Notion DBスキーマと使い方

---

## 重要な設計判断（忘れないこと）

1. **LoRAはFLUX（画像）でのみ使用**。Kling i2vにはLoRA不要（入力画像から顔を引き継ぐ）
2. **動画エンジンは差し替え可能**（Wan / Kling / Luma）— `image_url` と `prompt` は使い回せる
3. **素材は人間が作って貯める**。毎日の組み立てと投稿だけAnimaが自動化
4. **大きな動き（振り返り等）は避ける**。顔が崩れる
5. **カメラ動作はデフォルトで入る**。プロンプトで明示的に抑制が必要

---

## LoRAファイルの管理

### ローカルバックアップ（必ず保持）

```
~/.animaworks/common_knowledge/tiktok_templates/kyoka/lora/
├── kyoka_flux_lora_v1.safetensors        # LoRA本体（約90MB）
└── kyoka_flux_lora_v1_config.json        # 学習時の設定情報
```

### 現在使用中のCDN URL

```
https://v3b.fal.media/files/b/0a966fb0/hxvTK_oyDRAWRd_JLOMQH_pytorch_lora_weights.safetensors
```

FLUX JSONの `loras[0].path` に指定する。

### URLが期限切れになった場合の復旧手順

1. ローカルの `kyoka_flux_lora_v1.safetensors` を fal.ai Web UIの「Storage」または Python SDK `fal_client.upload_file()` で再アップロード
2. 返ってきた新URLを取得
3. SKILL.md の標準JSONテンプレートと asset_pool.json を新URLに更新

### 学習時の情報（config.jsonより）

| 項目 | 値 |
|------|-----|
| モデル | fal-ai/flux-lora-fast-training |
| Trigger Word | `kyoka` |
| Steps | 1471 |
| 学習日 | 2026-04-16 |
