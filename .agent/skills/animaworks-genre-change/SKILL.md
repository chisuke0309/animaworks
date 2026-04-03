---
name: animaworks-genre-change
description: >
  AnimaWorksのX投稿パイプラインを別ジャンルに切り替えるためのスキル。
  修正対象ファイルの特定、修正手順、確認チェックリストを提供する。
  コード変更は不要。テキスト文書（injection.md, cron.md, knowledge/*.md）のみ修正。
metadata:
  model: sonnet
risk: low
source: trinitydox
---

## このスキルを使う場面

- AnimaWorksのX投稿ジャンルを変更するとき（例：ペット→AI活用術、転職、美容など）
- 新しいアカウント/ブランド向けにナレッジを入れ替えるとき
- 既存パイプラインの構造を維持したまま、コンテンツテーマだけ差し替えるとき

## 使わない場面

- AnimaWorksのコード自体を修正するとき（コードにジャンル依存なし）
- 投稿スケジュール（08:00/17:00）や投稿フロー自体を変えるとき
- Anima構成（cicchi/rue/kuro/sora）を増減するとき

---

## 前提知識

### パイプライン構造（ジャンル非依存）

```
rue (調査) → cicchi (管理) → kuro (制作) → x_post_save_pending → 承認 → 自動投稿
```

この構造はジャンルに依存しない。変えるのは「何について書くか」のナレッジだけ。

### ファイル構成の原則

| ディレクトリ | 役割 | ジャンル依存 |
|---|---|---|
| `identity.md` | キャラクター定義（名前・性格・口調） | ほぼなし |
| `injection.md` | 行動指針・専門領域の定義 | **あり**（領域記述） |
| `cron.md` | スケジュール・LLMへの指示文 | **あり**（指示文にジャンル名） |
| `knowledge/*.md` | 学習済みナレッジ・ニッチ分析 | **あり**（内容が全てジャンル固有） |
| `procedures/*.md` | 作業手順書 | ほぼなし |

---

## Step 1: 新ジャンルの定義

以下を決定してから作業を開始する：

```
ジャンル名:（例：AI活用術 / 転職 / 美容 / ダイエット / 育児）
ブランド名:（例：TrinityDox）
ターゲット:（例：30代会社員 / 子育て中の主婦）
口調:（例：親しみやすい / 専門的）
ハッシュタグ戦略:（必須タグ + テーマタグ + リーチタグ）
```

---

## Step 2: 必須修正（7ファイル）

### 2-1. cicchi/injection.md

**修正箇所**: ジャンル記述（2箇所程度）

```
変更前: ペット・グルーミング／エコ・サステナブル生活術コンテンツ事業の推進
変更後: {新ジャンル}コンテンツ事業の推進
```

### 2-2. cicchi/cron.md

**修正箇所**: rueへの指示文（morning枠・evening枠の2箇所）

```
変更前: 「ペット・グルーミング／エコ・サステナブル生活術のトレンドを調査し...」
変更後: 「{新ジャンル}のトレンドを調査し...」
```

### 2-3. cicchi/identity.md

**修正箇所**: ジャンル記述（1箇所）

### 2-4. kuro/injection.md

**修正箇所**: 専門領域の記述（2箇所程度）

```
変更前: ペット・グルーミング／エコ・サステナブル生活術のX・TikTokコンテンツを支える
変更後: {新ジャンル}のX・TikTokコンテンツを支える
```

### 2-5. rue/injection.md

**修正箇所**: 専門領域の記述（1箇所）

### 2-6. rue/cron.md

**修正箇所**: ニッチ定義の記述

### 2-7. shared/pipelines/x_post.md

**修正箇所**: ブランド説明・ジャンル定義・ニッチ例（大部分を書き換え）

```
変更前:
  **ブランド**: TrinityDox｜癒しと暮らしのヒント
  **ジャンル**: ペット・グルーミング＋エコ・サステナブル生活術

変更後:
  **ブランド**: {ブランド名}
  **ジャンル**: {新ジャンル}
```

---

## Step 3: 旧ナレッジ削除（約16ファイル）

以下は旧ジャンルの学習データ。新ジャンルでは不要なので削除する。

### cicchi/knowledge/ から削除

```bash
# ニッチ分析ファイル（旧ジャンル固有）
rm ~/.animaworks/animas/cicchi/knowledge/niche*.md
```

### kuro/knowledge/ から削除

```bash
# グルーミング特化パターン
rm ~/.animaworks/animas/kuro/knowledge/grooming-*.md
rm ~/.animaworks/animas/kuro/knowledge/niche*.md
```

### rue/knowledge/ から削除

```bash
# 旧ニッチ候補・トレンド分析
rm ~/.animaworks/animas/rue/knowledge/*-niche-selection.md
rm ~/.animaworks/animas/rue/knowledge/surveyed-topics.md
```

### shared/pipelines/ から削除

```bash
# 旧ジャンルのパイプライン分析
rm ~/.animaworks/shared/pipelines/trinity*.md
rm ~/.animaworks/shared/pipelines/trinitybox*.md
```

---

## Step 4: 部分修正（2ファイル）

### cicchi/knowledge/morning_content_strategy.md

- **構成原則（実行性・シンプルさ・即座の効果・行動喚起）**: そのまま維持
- **具体例**: 旧ジャンルの例を削除し、新ジャンルの例に差し替え

### rue/knowledge/niche-selection-criteria.md

- **評価軸（実践性・差別化・医療価値・SNS適性）**: そのまま維持（「医療価値」は新ジャンルに応じて調整）
- **具体例**: 旧ジャンルの例を削除し、新ジャンルの例に差し替え

---

## Step 5: 修正不要（確認のみ）

以下はジャンル非依存なので修正不要。変更しないこと。

| ファイル | 理由 |
|---------|------|
| `*/identity.md`（sora, kuro, rue） | キャラクター定義はジャンル不問 |
| `sora/injection.md`, `sora/cron.md` | ビジュアル生成はジャンル不問 |
| `cicchi/knowledge/posting_rule.md` | 投稿ルール（枠・上限・ハッシュタグ）は汎用 |
| `sora/knowledge/*.md` | TikTok画像生成・コミュニケーション戦略は汎用 |
| コード全般（`core/`, `server/`） | ジャンル固有のハードコードなし |

---

## Step 6: 記憶のクリーンアップ

ジャンル変更後、旧ジャンルの記憶が search_memory 経由で再出現しないよう、以下をクリーンアップする：

```bash
for anima in cicchi rue kuro sora; do
  BASE=~/.animaworks/animas/$anima

  # episodes 削除（旧ジャンルの日次サマリー）
  rm -f $BASE/episodes/*.md

  # vectordb 削除（旧ジャンルのembedding）
  rm -rf $BASE/vectordb && mkdir -p $BASE/vectordb

  # index_meta.json リセット
  echo '{}' > $BASE/index_meta.json
done
```

**注意**: activity_log は削除不要（HEARTBEAT_OK化で十分）。詳細手順はMEMORY.mdの「全Animaクリーンアップ手順」を参照。

---

## Step 7: 確認テスト

1. サーバー再起動: `launchctl kickstart -k gui/$(id -u)/com.animaworks.server`
2. Knowledge Lint 実行: `uv run python scripts/knowledge_lint.py --json`
   - critical が 0 であること
3. 次のcronサイクル（09:00 or 21:00）で投稿パイプラインが正常動作すること
4. Telegram通知にスコアが表示されること
5. 投稿内容が新ジャンルに沿っていること

---

## チェックリスト

- [ ] 新ジャンル・ブランド名・ターゲットを決定
- [ ] cicchi: injection.md, cron.md, identity.md を修正
- [ ] kuro: injection.md を修正
- [ ] rue: injection.md, cron.md を修正
- [ ] shared/pipelines/x_post.md を修正
- [ ] 旧ニッチファイル削除（cicchi/kuro/rue/shared）
- [ ] morning_content_strategy.md の例を差し替え
- [ ] niche-selection-criteria.md の例を差し替え
- [ ] 記憶クリーンアップ（episodes, vectordb, index_meta）
- [ ] サーバー再起動
- [ ] Knowledge Lint 実行（critical 0確認）
- [ ] 投稿パイプライン動作確認
