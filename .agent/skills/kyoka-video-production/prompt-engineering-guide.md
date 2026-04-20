# Prompt Engineering Guide — Kyoka動画生成

fal.ai FLUX + Kling i2v パイプライン用のプロンプト設計ノウハウ。
2026-04-17 の試作で得た知見を体系化。

---

## FLUX画像プロンプトの鉄則

### 必ず含めるワード（鏡花らしさの維持）

| カテゴリ | 必須ワード |
|---------|----------|
| **トリガー** | `kyoka` |
| **表情** | `piercing intense gaze, fierce mysterious expression` |
| **着物** | `traditional Japanese kimono, obi sash, black kimono with gold peony embroidery` |
| **画質** | `ultra-realistic, photographic, 8K` |

### 絶対に入れないワード（世界観破壊）

| ワード | 理由 |
|-------|------|
| `calm serene expression` | 鏡花は冷徹・鋭い。穏やかな表情は別キャラ |
| `smiling, warm` | 同上 |
| `cartoon, anime` | フォトリアル路線 |
| `western dress, gown` | 着物がドレス化する |

### ⚠️ FLUXはnegative_promptを受け付けない

FLUX系エンドポイント（`fal-ai/flux-lora` 等）は **`negative_prompt` フィールドを無視します**。
避けたい要素は、positive prompt に**反対表現**を明示することで対処する。

| 避けたい要素 | positive promptに書く対処 |
|------------|-------------------------|
| 洋服・ドレス化 | `traditional Japanese kimono, obi sash` を強く明示 |
| 笑顔 | `fierce mysterious expression, no smile, serious face` |
| アニメ調 | `ultra-realistic, photographic` |
| 柔らかい表情 | `piercing intense gaze, sharp features` |
| ぼやけ | `sharp focus, high detail` |

**原則**: 「出すな」ではなく「こう出せ」で書く。

---

## Kling i2v動画プロンプトの鉄則

### 動きを制御する3原則

#### 1. 静止を強制する定型文

```
standing completely still, Fixed camera, no zoom, no pan
```

この3要素を必ず入れる。特に `Fixed camera, no zoom, no pan` はカメラ暴走を抑えるのに効く。

#### 2. 被写体動作は主語付きで明示

❌ 悪い例: `turning around slowly, dramatic reveal`  
→ カメラ動作として解釈される

✅ 良い例: `She slowly raises her hand and touches a cherry blossom petal`  
→ 「She」で主語を固定し、具体的な動作を指示

#### 3. 顔の固定を明示

```
her eyes remain piercing and locked on the camera
perfect face consistency throughout
```

i2vは新しい角度の顔を「作る」ため、明示的に固定を指示すると安定する。

### ネガティブプロンプト定番（Klingは受け付ける）

```
blur, distort, low quality, face change, inconsistent features, camera zoom, camera pan, camera movement, dolly
```

**特に重要な追加項目:**
- `camera zoom, camera pan, camera movement, dolly` — カメラ暴走を抑える
- `face change, inconsistent features` — 顔変化を抑える

**注意**: FLUXと違いKlingは `negative_prompt` を正しく受け付けます。

---

## tail_image_url 運用の鉄則

2枚のFLUX画像を `image_url` と `tail_image_url` で指定する場合の必須事項。

### 大原則: LoRAで固定されない全要素を揃える

LoRAが固定するのは**顔の特徴のみ**。以下の要素はプロンプトで明示的に統一する必要がある:

| 要素 | 両プロンプトに書くべき具体度 |
|------|---------------------------|
| 髪型 | 長さ・分け目・結い方・アクセサリーまで一字一句同じ |
| 着物 | 柄・袖の長さ・帯の有無まで |
| 小物 | 持ち物・アクセサリー・装飾品 |
| 背景 | 場所・時間帯・光源まで |

### 髪型の統一指示テンプレート（FLUX prompt向け）

FLUXはネガティブ不可なので、**避けたい髪型は positive prompt に「〜でない」形で明示**する。

#### ストレート・ロング（無装飾）
```
long straight jet-black hair with a center part, falling smoothly down past her shoulders, 
no hair accessories, no hair ornaments, no bun, no ponytail, no updo, no hairpins, 
hair draped naturally behind her back
```

#### 結い上げ（かんざし装飾）
```
hair tied up in a high bun with traditional Japanese kanzashi hairpins, 
decorative red flowers in hair, elegant updo, no loose hair, no hair down
```

**ポイント**: `no bun`, `no loose hair` 等を positive 側に入れることで、FLUXに「これは除外」の信号を送れる。

### 検証チェックリスト（2枚のFLUX画像生成後）

**Klingに投入する前に必ず確認すること:**

- [ ] 顔の特徴が一致している（LoRAで固定済みのはず）
- [ ] **髪型が一致している**（長さ・結い方・アクセサリー）
- [ ] 着物の色・柄が一致している
- [ ] 帯の有無・位置が一致している
- [ ] アクセサリー（かんざし・扇子等）の有無が一致している
- [ ] 背景の雰囲気が近い（完全一致でなくても可）

いずれか不一致なら、FLUXプロンプトを修正して再生成。Klingは**細部の不一致を補間で吸収できない**（モーフィングとして出てしまう）。

---

## cfg_scale の使い分け

| 値 | 挙動 | 用途 |
|----|------|------|
| 0.3〜0.5 | プロンプト弱め、モデルの創造性重視 | 雰囲気重視・微調整したくない時 |
| **0.7〜0.9** | **プロンプト強め、指示に忠実** | **通常はこれを推奨** |
| 1.0 | プロンプト最強、他要素は無視気味 | 特定の動きを絶対させたい時 |

**初期値は `0.9` を推奨**。動きが出すぎる場合は下げる。

---

## 知見サマリ（試行錯誤から）

### 得た学び

1. **"turning around" は顔が崩れる** — 大きな動きは入力画像にない角度を「捏造」するためLoRA顔から逸脱
2. **"right hand only" などの単独指示は守られにくい** — Klingは「両手で」動かしがち
3. **カメラ動作がデフォルト優先** — 明示的にネガティブに入れないと勝手にズームアウトする
4. **"calm serene" と "intense eye contact" は矛盾** — 表情ワードは統一すること
5. **画質ワード（8K, highly detailed）はi2vでは無意味** — 入力画像で既に決まっている
6. **Klingは入力画像のアスペクト比を自動継承** — `aspect_ratio` フィールドは存在しない

### i2vモデル横比較（2026-04時点）

| モデル | 価格 | 顔一貫性 | 備考 |
|--------|------|---------|------|
| Wan 2.2 | $0.10/秒 | △ 振り返り中に顔変化 | 安いがKyokaには不十分 |
| **Kling v2.5 Turbo Pro** | **~$0.35/秒** | **◎ 静止＋微動なら崩れない** | **採用** |
| LTX-2.3 22B | 中 | - | 品質がいまいち |
| Luma Dream Machine | 中 | 未検証 | 次回候補 |

---

## 季節別フレーバー

現在の季節パラメータは `season_context.json` を参照。
現時点（2026-04）は `late_spring`（散り桜）。

### 晩春（散り桜）

**FLUX追加ワード:**
```
cherry blossom petals falling, pink petals drifting in air, late spring night, ephemeral beauty
```

**Kling追加ワード:**
```
cherry blossom petals falling slowly and gracefully around her, petals swirling gently
```

---

## よくある失敗と対処

| 症状 | 原因 | 対処 |
|------|------|------|
| カメラがズームアウトする（Kling） | プロンプトにカメラワーク寄り語 | `Fixed camera, no zoom, no pan` 追加 + **Klingのネガティブに** `camera zoom` |
| 顔が途中で変わる（Kling） | 動きが大きい | より小さい動作に変更 / tail_image_url方式 / cfg_scale上げる |
| 着物がドレス化（FLUX） | FLUXはネガティブ不可 | positive に `traditional Japanese kimono, obi sash, no western dress` を強く明示 |
| 笑っている（FLUX） | 表情ワードの曖昧さ | positive に `fierce mysterious expression, no smile, serious face` を明示 |
| 両手が同時に動く（Kling） | 片手指定が守られず | 「片手だけ」は諦める。両手動作として成立する構図を選ぶ |
| 開始と終了で髪型違う（tail_image_url） | FLUXプロンプト不一致 | 両プロンプトで髪型指示を完全統一する |
