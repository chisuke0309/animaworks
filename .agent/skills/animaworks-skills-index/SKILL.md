---
name: animaworks-skills-index
description: >
  AnimaWorks関連の全スキルの目次。スキルは3箇所に分散しているため、
  AnimaWorksの作業を始める前にこのインデックスを確認し、関連スキルを参照すること。
  「animaworks」「anima」「事業部」「投稿」「cron」「ツール」等の作業で使用。
metadata:
  model: haiku
risk: low
source: trinitydox
---

## このスキルを使う場面

- AnimaWorksに関わる作業を始めるとき（まずここで関連スキルを探す）
- 「このスキルあったっけ？」と思ったとき
- 新しいスキルを作った後、ここに登録するとき

## 重要: なぜこの目次が必要か

AnimaWorksのスキルは **3つの異なる場所** に存在し、用途と利用者が異なる。
目次なしでは、存在するスキルを見落として同じ罠にはまる。

---

## スキル配置の3層構造

| 場所 | 用途 | 利用者 |
|------|------|--------|
| `.agent/skills/` (プロジェクト内) | 運用・管理スキル（AnimaWorks固有） | Claude Code / Gemini CLI / 人間 |
| `~/.animaworks/common_skills/` | AnimaWorks内蔵スキル | Anima（LLM）自身 |
| `~/.animaworks/animas/{name}/skills/` | Anima個別スキル | 特定のAnima |

**新しいスキルを作るとき:**
- Claude Code / 人間が使う（AnimaWorks固有） → `.agent/skills/{skill-name}/SKILL.md`
- どのプロジェクトでも使える汎用スキル → `~/trinitydox-standards/skills/`
- Anima自身が使う → `templates/ja/common_skills/{name}/`（OSS）→ デプロイで `~/.animaworks/common_skills/` にコピー
- 特定Animaだけが使う → `~/.animaworks/animas/{name}/skills/`

---

## 一覧: 運用・管理スキル（Claude Code / 人間向け）

保存先: `.agent/skills/`

| スキル名 | 用途 | 使う場面 |
|----------|------|---------|
| **animaworks-skills-index** | この目次 | AnimaWorks作業の最初に |
| **animaworks-new-unit** | 新事業部の新設 | Animaチームを新しく作るとき |
| **animaworks-genre-change** | X投稿ジャンル変更 | コンテンツテーマを切り替えるとき |
| **animaworks-promo** | プロモ素材生成 | WEBサイト・資料にAnimaWorksを紹介するとき |

## 一覧: AnimaWorks内蔵スキル（Anima自身が使う）

保存先: `~/.animaworks/common_skills/`（テンプレート元: `templates/ja/common_skills/`）

| スキル名 | 用途 | 使う場面 |
|----------|------|---------|
| **newstaff** | 新Anima雇用（ヒアリング→キャラクターシート→CLI作成→bootstrap） | 新メンバーを追加するとき |
| **cron-management** | cron.mdの正しい記法 | cronタスクの追加・変更・削除 |
| **animaworks-guide** | CLIクイックリファレンス | animaworksコマンドの使い方 |
| **subordinate-management** | 部下Animaの管理（休止・復帰・モデル変更・再起動・委譲・状態確認） | プロセス管理全般 |
| **tool-creator** | ツールモジュール作成 | 新しいPythonツールを追加するとき |
| **skill-creator** | スキルファイル作成 | 新しいSKILL.mdを作るとき |
| **image-posting** | 画像添付 | チャット応答に画像を添付 |
| **subagent-cli** | 外部AIサブエージェント | codex exec等を使うとき |

## 一覧: Anima個別スキル

保存先: `~/.animaworks/animas/{name}/skills/`

現在、個別スキルはなし（全て common_skills に統合済み）。
今後Anima固有のスキルが必要になった場合のみここに配置する。

---

## 相互参照マップ

スキル間の依存・参照関係:

```
animaworks-new-unit
  ├── 参照: cron-management（cron.md記法）
  ├── 参照: tool-creator（ツールモジュール実装）
  └── 参照: subordinate-management（Anima管理）

animaworks-genre-change
  ├── 参照: cron-management（cron.md修正）
  └── 関連: animaworks-promo（プロモ素材更新）
```

**作業前に相互参照を確認すること。** 単独スキルだけ見て作業すると、
関連スキルに書かれたルール（例: cron.mdのH2必須ルール）を見落とす。

---

## メンテナンスルール

- 新しいAnimaWorks関連スキルを作ったら、**必ずこの目次に追記する**
- 年に1回、全スキルの棚卸しを行い、廃止・統合を検討する
- スキルを廃止する場合は目次から削除し、ファイルも削除する
