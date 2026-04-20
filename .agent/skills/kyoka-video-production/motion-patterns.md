# Motion Patterns — 動きパターンカタログ

Kyoka動画で試した動きパターンの成功／失敗カタログ。
新しいパターンを試したら必ずここに追記。

---

## ✅ 成功パターン

### #001 — 静止＋ズームアウト＋花びら

**特徴**: 鏡花が直立不動、カメラがゆっくり引き、花びらが舞う

**FLUXプロンプト例:**
```
kyoka, close-up portrait, hands lowered at her sides, piercing intense gaze at camera, 
fierce mysterious expression, black kimono with gold peony embroidery, 
cherry blossom petals falling gently around her, pink petals in air, 
late spring night, dark background, traditional Japanese kimono, obi sash, 
ultra-realistic, photographic, 8K
```

**Klingプロンプト例:**
```
A beautiful woman in a traditional black kimono standing completely still facing 
the camera directly, piercing intense gaze at the viewer, fierce mysterious expression, 
subtle gentle wind slowly blowing her hair strands, kimono sleeves gently rippling, 
cherry blossom petals falling slowly and gracefully around her, very subtle natural 
breathing and micro chest movement, perfect face consistency throughout, cinematic 
lighting, dramatic elegant atmosphere
```

**結果**: 顔一貫性◎ / 世界観◎ / カメラがズームアウトする副作用あるが演出として成立

**用途**: ミステリアスな登場シーン・静謐な1カット

---

### #002 — 両手で口元を隠す所作

**特徴**: 鏡花が両手・袖を口元の前に上げる伝統的な所作

**FLUXプロンプト（開始ポーズ）:**
```
kyoka, close-up portrait, hands lowered at her sides, piercing intense gaze at camera, 
fierce mysterious expression, black kimono with gold peony embroidery, 
long sleeves hanging down, cherry blossom petals falling gently around her, 
pink petals in air, late spring night, dark background, 
traditional Japanese kimono, obi sash, ultra-realistic, photographic, 8K
```

**Klingプロンプト:**
```
A beautiful woman in a traditional black kimono slowly raising her right hand 
toward her face, her long kimono sleeve following the motion gracefully, 
covering the lower half of her face partially, her eyes remain piercing and 
locked on the camera, subtle wind blowing hair strands, cherry blossom petals 
falling slowly and gracefully around her, very subtle natural breathing, 
perfect face consistency throughout, cinematic lighting, dramatic elegant atmosphere. 
Fixed camera, no zoom, no pan.
```

**結果**: 顔一貫性◎ / 動き◎ / プロンプトは「片手」指定だが両手動作になった — ただし伝統的所作として成立

**用途**: ミステリアス＋所作が欲しい1カット・意味深な動画

**教訓**: Klingは「片手だけ」の指示を守らない。両手動作を前提に構図を設計する方が確実。

---

### #003 — 肩越し振り返り → 正面（tail_image_url方式・確立版）

**特徴**: 右肩越しに睨んでいる状態から、ゆっくり回転して正面を向く大きな振り返り動作。鏡花のミステリアスさを最大限に表現できる決定打パターン。

**成功の鍵**:
1. **tail_image_url を使って両端の顔をLoRAで固定**
2. **髪飾りを超具体的にプロンプト指定**（個数・位置・飾りの内容まで）
3. **両プロンプトで同じseedを使用**
4. フル後ろ姿ではなく**肩越し**にすることで、顔の一部が見えた状態からスタート

**Step 1a: FLUX 開始画像（肩越し・右肩から後ろを見る）**
```
kyoka, upper body portrait, standing in misty Kyoto alley at night, 
back turned to camera, view from behind, 
long black hair tied in a low bun at the back of her neck, 
exactly two traditional Japanese red kanzashi hairpins on the right side of her head, 
one kanzashi decorated with a single red chrysanthemum flower, no other hair accessories, 
black kimono with gold peony embroidery, lantern light casting shadows, 
cherry blossom petals falling, pink petals in air, late spring night, 
traditional Japanese kimono, obi sash tied at her back, 
ultra-realistic, photographic, 8K
```
Seed: `42`（終了画像と同じ値）

※結果として「フル後ろ姿」にはならず、「肩越しに睨む」構図になることが多い。これがむしろ良い。

**Step 1b: FLUX 終了画像（正面）**
```
kyoka, upper body portrait, standing in misty Kyoto alley at night, 
facing camera directly, piercing intense gaze at viewer, fierce mysterious expression, 
long black hair tied in a low bun at the back of her neck, 
exactly two traditional Japanese red kanzashi hairpins on the right side of her head, 
one kanzashi decorated with a single red chrysanthemum flower, no other hair accessories, 
black kimono with gold peony embroidery, lantern light casting shadows, 
cherry blossom petals falling, pink petals in air, late spring night, 
traditional Japanese kimono, obi sash, ultra-realistic, photographic, 8K
```
Seed: `42`（開始画像と同じ値）

**Step 2: Kling v2.5 Turbo Pro**
```json
{
  "prompt": "She slowly turns from her over-the-shoulder glance to face the camera directly. Her long hair and hair ornaments catch the light as she rotates. Her piercing gaze remains locked on the viewer throughout the entire motion. Her black kimono sleeve trails gracefully. Cherry blossom petals swirl around her during the rotation. Smooth continuous turn.",
  "image_url": "{{Step1aの肩越し画像URL}}",
  "tail_image_url": "{{Step1bの正面画像URL}}",
  "duration": "5",
  "negative_prompt": "abrupt motion, teleport, face morph, distorted face, blurry face, flickering, different face, changing accessories",
  "cfg_scale": 0.7
}
```

**結果**: 
- 顔一貫性: ◎
- 髪飾り一貫性: ◎
- 回転の滑らかさ: ◎（右肩越し → 左回りで正面）
- ドラマ性: ◎（鏡花らしいミステリアスな登場）

**用途**: 動画の冒頭・印象的なフック・鏡花の「登場」シーン

**確立した方法論**:
1. 髪飾り・服装の細部まで**超具体的に指定**（個数・位置・飾りの内容）
2. 両プロンプトで**同じseed**を使用
3. ポーズ指定は `back turned to camera` 程度でよい（LoRAとseedが自動的に「肩越し」構図を選ぶ）
4. Kling には `negative_prompt: changing accessories` を入れて髪飾りの一貫性をさらに強制

---

## ❌ 失敗パターン

### ×001 — 振り返り（単一画像）

**試行内容**: 背中から振り返って正面を向く動き（開始画像1枚のみ指定）

**問題点**: 
- 振り返り後の正面顔がLoRA顔から微妙にズレる
- 大きな動き（体の回転）は入力画像にない角度を「作る」ため顔が不安定

**解決策の試み**: → ×002（tail_image_url方式）へ

---

### ×002 — 振り返り（tail_image_url方式・髪型不一致）

**試行内容**: 後ろ姿→正面の大回転。Kling v2.5 Turbo Pro の `tail_image_url` で両端の顔をLoRAで固定。

**結果**: 
- 顔の一貫性: ◎（LoRAで両端固定）
- 動きの自然さ: ◎（Klingが補間）
- **髪型の一貫性: ✗ — 開始と終了で髪型が違う**
  - 後ろ姿画像: 長いストレートで背中に流れる髪
  - 正面画像: 別の髪型（結い上げ or 分け目違い等）
- 回転の途中で髪型がモーフィングして不自然

**根本原因**: 
- LoRAは**顔のみ**を固定する。髪型・服装の細部は固定しない
- 「long black hair」程度の指示では、FLUXは2枚で別の髪型を生成する
- Klingはその差異を補間しようとするが、髪は途中で別物に変わる

**解決済み**: #003 の手法（髪飾りを超具体指定＋同一seed）で解決。

**試したが効果が薄かった方法**:
- img2img で2枚目を1枚目から派生（ポーズ大転換には不適・構図が維持されすぎる）

---

### ×002 — 大きいモーション（歩く・走る）

**試行内容**: なし（理論上避けるべきパターン）

**理由**: 歩行・体の大きな移動は背景との整合性が取れず破綻する可能性が高い。
歩行を演出したい場合は、**カメラが被写体から離れる（ズームアウト）** で擬似的に表現する方が安全。

---

## 🔬 未検証パターン（今後試す候補）

### 未検証-001 — 首をゆっくり傾ける

**期待する動き**: 鏡花が首を左右に微かに傾けながら目線を保つ

**Klingプロンプト案:**
```
A beautiful woman in a traditional black kimono tilting her head slowly to the side, 
her gaze remaining locked on the camera throughout, hair falling softly with the motion, 
kimono sleeve gently moving, cherry blossom petals falling around her, 
perfect face consistency, Fixed camera, no zoom, no pan.
```

### 未検証-002 — 目線だけ動かす

**期待する動き**: 顔は正面のまま、目だけ左右に動く

**Klingプロンプト案:**
```
A beautiful woman in a traditional black kimono standing completely still, 
her head remains fixed facing forward, only her eyes slowly shifting to look 
to the left then back to the camera, piercing gaze, fierce expression, 
cherry blossom petals falling, Fixed camera, no zoom, no pan.
```

### 未検証-003 — 扇子を開く

**期待する動き**: 手に持った扇子をゆっくり広げる

**必要準備**: FLUX画像で扇子を持った鏡花を生成する必要あり

---

## パターン追加時のチェックリスト

新しいパターンを本カタログに追加するとき:

- [ ] FLUXプロンプト（開始フレーム）を明記
- [ ] Klingプロンプトを明記
- [ ] 結果の評価（顔一貫性・動き・世界観）
- [ ] 用途（どのシーンに使えるか）
- [ ] 教訓（次回のための学び）
- [ ] asset_pool.json にエントリ登録
- [ ] Notion DBにパターンとして記録
