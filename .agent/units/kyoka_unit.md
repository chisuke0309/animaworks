---
unit: kyoka
status: 中止
updated: 2026-05-04
---

# Kyoka事業部 — 中止

## 中止の経緯（2026-05-04 chisuke判断）

> 私が美女動画で収益化を言い出したんだが、それほど甘くはないってことがいまさらながらよくわかった。なのでImage⇛Seedance2で精密な動画ができることがわかっただけでOKとし、一旦はKyokaプロジェクトは中止にします。

きっかけ: scenario_003 が新アカ @kisaragikyokaoffice で90回視聴まで届いたが、冒頭数秒で離脱が続き、平均視聴秒数が伸びず拡散しなかった。美女動画ジャンルの競合過多 × 収益化ハードルの高さを実感。

## 残った資産（学び）

- **Image → Seedance 2.0 で精密な15秒動画が作れることを確認した**（GPT Image 2.0 の6フレーム絵コンテ → Seedance 2.0 BGM自動付与）
- TikTok Studio がAIラベルトグルを持たず、ラベル無し投稿で再生0シャドウバンになる仕様を把握（→ auto-memory `feedback_tiktok_ai_label.md`）
- Notionスキーマは `notion-update-data-source` の ADD COLUMN で後から追加できる
- GPT Image Prompt は参照画像アンカー＋FACE CONSISTENCY指示が必須（無いと別人が生成される）

## 中止に伴うクリーンアップ（2026-05-04 実施）

- Anima削除: rin / kiri / sumi（`~/.animaworks/animas/` から削除）
- `~/.animaworks/config.json` から rin / kiri / sumi のエントリ削除
- `~/.animaworks/common_knowledge/organization/goals.md` から Kyoka事業部セクション（L122-202）削除

## 未対応（chisuke判断待ち）

- TikTok @kisaragikyokaoffice / Instagram @kyokakisaragi.ai アカウントの扱い（休眠・削除・非公開化のいずれにするか）
- 動画素材（scenario_001〜005）の保存先 `~/.animaworks/common_knowledge/tiktok_templates/kyoka/assets/` をどうするか
- Notion DB `Kyoka Scenarios` ([リンク](https://www.notion.so/f1d407fcb3d94ca78cd81ddbe2c11d67)) をどうするか
