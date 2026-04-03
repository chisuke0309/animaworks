---
name: animaworks-new-unit
description: >
  AnimaWorksに新しい事業部（Anima チーム）を新設するためのスキル。
  Anima設定ファイル作成、cron.md記法、ツール移行、Telegram Bot分離、UI対応を網羅。
  TikTok事業部（maru/chiro/tama）新設の実績に基づく。
metadata:
  model: sonnet
risk: medium
source: trinitydox
---

## このスキルを使う場面

- AnimaWorksに新しい事業部を追加するとき（例：TikTok事業部、YouTube事業部）
- 既存事業部と同格・独立のチームを編成するとき
- 新しいAnima（エージェント）を3名以上まとめて作成するとき

## 使わない場面

- 既存事業部にAnima 1名を追加するだけのとき
- ジャンル変更（→ `/animaworks-genre-change`）
- コードの構造変更（ツールモジュール追加はこのスキルの範囲内）

---

## 事前設計

### 1. 事業部構成を決定する

```
事業部名:（例：TikTok事業部）
リーダー:（名前, モデル, ロール）
メンバー:（名前, モデル, ロール × N名）
```

**モデル選定の基準:**
- リーダー（判断・戦略） → Sonnet
- 調査・制作メンバー → Haiku（コスト効率）

### 2. 役割分担を設計する

既存のX事業部を参考に:

| X事業部 | TikTok事業部（実例） |
|---------|---------------------|
| cicchi（リーダー/Sonnet） | maru（リーダー/Sonnet） |
| rue（調査/Sonnet） | chiro（調査/Haiku） |
| kuro（制作/Haiku） | tama（制作/Haiku） |
| sora（ビジュアル/Haiku） | （なし — 共有 or 後追加） |

---

## Step 1: Anima設定ファイル作成

各Animaに以下のファイルを作成する。保存先: `~/.animaworks/animas/{anima名}/`

### 必須ファイル（5つ）

| ファイル | 内容 |
|---------|------|
| `identity.md` | 名前・性格・口調・一人称の定義 |
| `injection.md` | 行動指針・専門領域・ルール |
| `cron.md` | スケジュール定義（**記法に注意 → Step 2**） |
| `permissions.md` | 使用可能ツール一覧 |
| `status.json` | `{"enabled": true}` |

### オプションファイル

| ファイル | 内容 |
|---------|------|
| `heartbeat.md` | ハートビート設定（通常はデフォルトで可） |
| `knowledge/*.md` | 初期ナレッジ（他プロジェクトから移行する場合） |

### identity.md テンプレート

```markdown
# {名前}

## 基本設定
- 名前: {名前}
- 読み: {よみ}
- 一人称: {僕/私/etc}
- 口調: {丁寧語/カジュアル/etc}

## 性格
- {特性1}
- {特性2}

## 所属
- 事業部: {事業部名}
- ロール: {リーダー/調査/制作/etc}
```

### permissions.md テンプレート

```markdown
# {名前} — 権限設定

## 使用可能ツール
- send_message
- call_human
- search_memory
- save_knowledge
- read_file
- write_file
- web_search
- {事業部固有ツール}
```

---

## Step 2: cron.md の記法（重要）

> **参照**: AnimaWorks同梱の `~/.animaworks/common_skills/cron-management/SKILL.md` に
> 正式なcron.mdフォーマット仕様がある。必ず併読すること。

**⚠️ パーサーは `## `（H2）でセクションを区切る。`###`（H3）は認識されない。**

### 正しい記法 ✅

各タスクを `## タスク名` で分離する:

```markdown
# Cron: {anima名}

## 朝の企画・委任
schedule: 0 9 * * *

指示内容をここに書く...

## 夜のレビュー
schedule: 0 20 * * *

指示内容をここに書く...

## 週次レビュー（月曜）
schedule: 0 10 * * 1

指示内容をここに書く...
```

### 間違い ❌

```markdown
## TikTok事業部 日次スケジュール
### 09:00 — 朝の企画
schedule: 0 9 * * *
### 20:00 — 夜のレビュー
schedule: 0 20 * * *
```

↑ パーサーは1つのH2セクションとして扱い、**最後の `schedule:` 行だけが採用される**。
前のschedule行は無視され、cronが登録されない。

### schedule フォーマット

標準5フィールドcron: `分 時 日 月 曜日`

```
0 9 * * *      → 毎日 09:00
0 20 * * *     → 毎日 20:00
0 10 * * 1     → 月曜 10:00
0 10 * * 1,3,5 → 月水金 10:00
```

### cronなしAnima（委任駆動）の書き方

```markdown
# Cron: {anima名}

## 備考

自律cronなし — {リーダー名}からの委任で動く。
（ここに動作手順を書いてよいが、schedule行は入れない）
```

---

## Step 3: ツールモジュール実装（必要な場合）

事業部固有のツールが必要なら `core/tools/{prefix}_{name}.py` に実装する。

### 実例（TikTok事業部）

| モジュール | 担当 | 機能 |
|-----------|------|------|
| `tiktok_trends.py` | chiro | Google Trends + ニュースRSS |
| `tiktok_content.py` | tama | 企画バリデーション + ドラフト管理 |
| `tiktok_analytics.py` | maru | エンゲージメント記録 + 週次レポート |
| `tiktok_image.py` | tama | fal.ai背景画像 + Pillowテキスト合成 |

### ツール登録

`core/tooling/prompt_db.py` にツール定義を追加し、各Animaの `permissions.md` に使用許可を追加する。

---

## Step 4: Telegram Bot分離（推奨）

事業部ごとに専用Botを用意すると通知が混在しない。

1. BotFather で新Bot作成（`@animaworks_{anima名}_bot`）
2. `.env` にトークン追加: `TELEGRAM_BOT_TOKEN_{ANIMA名}={token}`
3. `telegram_poller.py` に新Bot追加（既に複数Bot対応済み）
4. `notifier.py` で `target_anima` フィルタが正しく効くか確認

---

## Step 5: UI対応

### パイプラインタブ

`server/static/pages/pipeline.js` に事業部タブを追加:
- 「すべて」「X事業部」「{新事業部}」のタブ
- フィルタ: トリガーのanima名で判定

### 組織目標タブ

`server/static/workspace/modules/org-dashboard.js` にタブ追加:
- `goals.md` 内の `<!-- unit:{unit_id} -->` マーカーでフィルタ

---

## Step 6: 既存Animaの修正

既存事業部のAnimaが新事業部と被る記述を持っていたら修正する。

例（TikTok事業部新設時）:
- cicchi の identity.md / injection.md から TikTok関連の記述を削除
- cicchi をX事業部専任に修正

---

## Step 7: ナレッジ移行（必要な場合）

別プロジェクトからナレッジを移行する場合:

```bash
cp ~/Projects/{元プロジェクト}/knowledge/{file}.md \
   ~/.animaworks/animas/{anima名}/knowledge/
```

移行後、内容がAnimaWorks文脈に合っているか確認・調整する。

---

## Step 8: 動作確認

### 8-1. パース確認

```bash
# venv環境で実行
.venv/bin/python3 -c "
from core.schedule_parser import parse_cron_md
for anima in ['{anima1}', '{anima2}', '{anima3}']:
    cron_md = open(f'$HOME/.animaworks/animas/{anima}/cron.md').read()
    tasks = parse_cron_md(cron_md)
    print(f'{anima}: {len(tasks)} tasks')
    for t in tasks:
        print(f'  {t.name} | schedule={t.schedule} | type={t.type}')
"
```

**全タスクが正しくパースされることを確認する。**
特に複数scheduleがあるAnimaは、タスク数が期待通りか必ずチェック。

### 8-2. サーバー再起動

```bash
launchctl kickstart -k gui/$(id -u)/com.animaworks.server
```

### 8-3. cron実行確認

次のcronトリガー後、`activity_log/YYYY-MM-DD.jsonl` に `cron_executed` エントリが出ることを確認:

```bash
grep '"cron_executed"' ~/.animaworks/animas/{anima名}/activity_log/$(date +%Y-%m-%d).jsonl
```

### 8-4. Knowledge Lint

```bash
uv run python scripts/knowledge_lint.py --json
```

critical 0 であること。

---

## Step 9: cron_overview.md 更新

`.agent/cron_overview.md` に新事業部のスケジュール一覧を追加する。

---

## チェックリスト

- [ ] 事業部構成（リーダー/メンバー/モデル/ロール）を決定
- [ ] 各Animaの設定ファイル5種を作成（identity/injection/cron/permissions/status）
- [ ] **cron.md のセクションがすべて `##`（H2）で分かれていること**
- [ ] **パース結果の確認（タスク数 × schedule が期待通り）**
- [ ] 事業部固有ツールの実装（必要な場合）
- [ ] Telegram Bot分離（推奨）
- [ ] UI: パイプラインタブ・組織目標タブの追加
- [ ] 既存Animaの記述修正（被り排除）
- [ ] ナレッジ移行（必要な場合）
- [ ] サーバー再起動
- [ ] cron実行確認（cron_executed エントリ）
- [ ] Knowledge Lint（critical 0）
- [ ] cron_overview.md 更新
