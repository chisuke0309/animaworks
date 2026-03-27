---
name: reorganize-team
description: AnimaWorksのAnimaチームを新しいミッション・役割に刷新するスキル。「チームを再編して」「Animaの役割を変えたい」「新しいニッチで始めたい」などのリクエストに使用する。
---

# AnimaWorks チーム再編スキル

既存のAnimaチーム（cicchi/rue/kuro/sora）の中身を入れ替えて新しいミッションに転換する。
ファイルを新規作成するのではなく、**既存ファイルを上書き編集**することが基本方針。

---

## 事前確認（ユーザーに聞くこと）

作業開始前に以下を確認する：

1. **新しいミッション・ジャンル**: 何を発信するアカウントにするか
2. **投稿プラットフォーム**: X のみ／TikTok のみ／両方
3. **各Animaの役割変更**: デフォルトは以下の通り（変更がある場合確認）
   - cicchi: 統括マネージャー（オーケストレーター）
   - rue: リサーチャー（トレンド・ニッチ調査）
   - kuro: ライター（コンテンツ制作）
   - sora: ビジュアルディレクター（画像生成）
4. **既存コンテンツの扱い**: 全削除 or 一部保持
5. **アカウント情報**: X/TikTokアカウント名・bio等

---

## Step 1: 旧コンテンツの完全クリーンアップ

> ⚠️ **漏れやすい順番**: knowledge > assets > episodes > vectordb > activity_log
> この順番で必ず確認すること。episodesだけ消してもknowledge/assetsが残ると汚染が再生成される。

### 1-1. 旧Animaの「記憶」を消す

```bash
for anima in cicchi rue kuro sora; do
  BASE=~/.animaworks/animas/$anima

  # episodes（日次サマリー）削除
  rm -f $BASE/episodes/*.md && echo "$anima: episodes削除"

  # vectordb（ChromaDB）削除・再作成
  rm -rf $BASE/vectordb && mkdir -p $BASE/vectordb && echo "$anima: vectordb削除"

  # index_meta.json リセット
  echo '{}' > $BASE/index_meta.json && echo "$anima: index_meta.jsonリセット"

  # shortterm会話アーカイブ削除（⚠️ 旧セッションの文脈が大量に残る — 必ず削除）
  rm -f $BASE/shortterm/chat/archive/* 2>/dev/null && echo "$anima: shortterm archive削除"
done
```

### 1-2. 旧テーマのknowledgeファイルを確認・削除 ⚠️ 最重要

```bash
# 全animaのknowledgeファイルを一覧表示
for anima in cicchi rue kuro sora; do
  echo "=== $anima/knowledge ==="
  ls ~/.animaworks/animas/$anima/knowledge/ 2>/dev/null || echo "(なし)"
done
```

**判断基準**:
- 旧ミッションに特化した内容（テーマ記事・旧戦略メモ等）→ **削除**
- 運用ルール・行動規範等（anima-agnostic）→ 保持

> ⚠️ **特に見落としやすい**: `revenue_strategy.md`、`subordinate_report_verification.md` 等、名前が汎用的でも中身が旧ミッション内容のファイルに注意

```bash
# 削除例（ファイル名は実際のものに合わせて変更）
rm -f ~/.animaworks/animas/cicchi/knowledge/[旧ファイル名].md
rm -f ~/.animaworks/animas/rue/knowledge/[旧ファイル名].md
```

### 1-3. 旧テーマのassetsファイルを確認・削除 ⚠️

```bash
for anima in cicchi rue kuro sora; do
  echo "=== $anima/assets ==="
  ls ~/.animaworks/animas/$anima/assets/ 2>/dev/null | grep -v "avatar_\|prompt.txt" || echo "(旧ファイルなし)"
done
```

アバター画像（`avatar_*.png`）と `prompt.txt` 以外の旧テーマ素材は削除する。

### 1-4. x_post_log.md をリセット（トークン節約）

`knowledge/x_post_log.md` は **毎heartbeatでシステムプロンプトに丸ごと埋め込まれる**。
旧ミッションの投稿ログが残っていると：
1. 旧コンテンツ汚染の原因になる
2. トークンを無駄に消費する（14件 ≈ 4,000 chars）

→ **新ミッション開始時点で5件以内にリセット**する。

```bash
cat > ~/.animaworks/animas/cicchi/knowledge/x_post_log.md << 'EOF'
# X投稿ログ（ローリングウィンドウ: 最新5件のみ保持）

**管理ルール**: 5件を超えた古い行は削除する。エンゲージメント計測（18:00）で likes/RTs/impressions を埋める。

**ブランド**: [アカウント名]
**ジャンル**: [新しいジャンル]

| 日付 | トピック要約 | tweet_id | likes | RTs | impressions |
|------|------------|----------|-------|-----|-------------|
EOF
```

### 1-5. activity_logの旧日付ファイルを削除

旧テーマ時代の日付ファイルは**丸ごと削除**する（置換より確実）。

```bash
CUTOFF="2026-XX-XX"  # 再編開始日（YYYY-MM-DD形式）に変更すること

for anima in cicchi rue kuro sora; do
  LOGDIR=~/.animaworks/animas/$anima/activity_log
  for f in $LOGDIR/*.jsonl; do
    date=$(basename $f .jsonl)
    if [[ "$date" < "$CUTOFF" ]]; then
      rm -f "$f" && echo "削除: $anima/$date.jsonl"
    fi
  done
done
```

### 1-6. 当日のactivity_logの旧キーワードをHEARTBEAT_OKに置換

当日分のログに旧ミッションのキーワードが含まれる場合は置換する：

```python
python3 << 'EOF'
import json, os

ANIMAS = ["cicchi", "rue", "kuro", "sora"]
BASE = os.path.expanduser("~/.animaworks/animas")

# ⚠️ 旧テーマのキーワードに合わせて変更すること
BAD_KEYWORDS = ["旧キーワード1", "旧キーワード2"]

for anima in ANIMAS:
    logdir = f"{BASE}/{anima}/activity_log"
    if not os.path.isdir(logdir):
        continue
    for filename in sorted(os.listdir(logdir)):
        if not filename.endswith(".jsonl"):
            continue
        logfile = f"{logdir}/{filename}"
        lines = open(logfile).readlines()
        clean = []
        replaced = 0
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
                content = e.get("content", "") + e.get("summary", "")
                if any(k in content for k in BAD_KEYWORDS):
                    e["content"] = "HEARTBEAT_OK"
                    e["summary"] = "HEARTBEAT_OK"
                    replaced += 1
                clean.append(json.dumps(e, ensure_ascii=False))
            except:
                clean.append(line)
        open(logfile, "w").write("\n".join(clean) + "\n")
    print(f"{anima}: 置換完了")
EOF
```

### 1-7. task_queueのstaleタスクをcompletedに

```python
python3 << 'EOF'
import json, os
from datetime import datetime, timezone

ANIMAS = ["cicchi", "rue", "kuro", "sora"]
BASE = os.path.expanduser("~/.animaworks/animas")
now = datetime.now(timezone.utc).isoformat()

for anima in ANIMAS:
    path = f"{BASE}/{anima}/state/task_queue.jsonl"
    if not os.path.exists(path):
        continue
    lines = open(path).readlines()
    updated = []
    changed = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        entry = json.loads(line)
        if entry.get("status") in ("pending", "in_progress", "blocked"):
            entry["status"] = "completed"
            entry["updated_at"] = now
            changed += 1
        updated.append(json.dumps(entry, ensure_ascii=False))
    open(path, "w").write("\n".join(updated) + "\n")
    if changed:
        print(f"{anima}: {changed}件をcompletedに更新")
print("完了")
EOF
```

### 1-8. stateのリセット

```bash
for anima in cicchi rue kuro sora; do
  echo '{"messages":[]}' > ~/.animaworks/animas/$anima/state/conversation.json
  echo "status: idle" > ~/.animaworks/animas/$anima/state/current_task.md
  > ~/.animaworks/animas/$anima/state/pending.md
  rm -f ~/.animaworks/animas/$anima/state/background_tasks/pending/*.json 2>/dev/null
  echo "$anima: stateリセット完了"
done
```

---

## Step 2: 各Animaのアイデンティティ更新

### 2-1. identity.md（キャラクター設定）

`~/.animaworks/animas/<name>/identity.md` を編集する。

**更新が必要な箇所**:
- `## ミッション` — 新しいジャンル・目的
- `## 専門スキル` — 新ミッションに合ったスキル
- `## 現在のプロジェクト` — 新プロジェクト名
- 投稿ルール（⚠️ 必ず含めること）:

```markdown
## ⚠️ 投稿ルール（厳守）
- Xの投稿は「決められた時間に1つずつ」投稿する。一度に複数投稿は絶対NG
- 1日の投稿上限は3件まで。それ以上は絶対に投稿しない
- 初回投稿・新ジャンル開始時は必ずユーザーに内容を見せてから投稿する
- 投稿前に「これを投稿していいか？」とTelegramまたはDMで確認を取ること
```

### 2-2. injection.md（役割指針・行動原則）

`~/.animaworks/animas/<name>/injection.md` を編集する。

**更新が必要な箇所**:
- `専門領域` の旧ミッション記述
- `行動指針` の旧プロジェクト名・旧ドメイン記述（例: 「AI・DX領域」→「ペット・グルーミング／エコ生活術」）
- 「誰に何を委任するか」テーブルの説明文（必要に応じて）

**変えなくてよい箇所**:
- 委任ルール・コミュニケーションフロー（構造的ルールなので共通）
- セッション終了ルール・報告フォーマット等の運用規則

**cicchiには必ずX投稿承認フローセクションを追加すること**:

```markdown
## X投稿承認フロー（厳守）
1. X投稿前は必ず `x_post_request_approval(text)` でTelegramにユーザー確認を送ること
2. ユーザーからの返信がinboxに届いたら以下で判断する（大文字小文字・日本語どれでも可）：
   - **承認**: `ok` / `OK` / `Ok` / `はい` / `承認` / `投稿して` → `x_post_execute_pending()` を呼ぶ
   - **拒否**: `ng` / `NG` / `いいえ` / `キャンセル` / `やめて` → `x_post_cancel_pending()` を呼ぶ
3. 承認でも拒否でも、実行後にTelegramで結果を報告すること
```

### 2-3. permissions.md（外部ツールをホワイトリスト化）⚠️ トークン節約

`~/.animaworks/animas/<name>/permissions.md` の `外部ツール` セクションを **`- all: yes`から個別ホワイトリスト** に変更する。

> **理由**: `- all: yes` にすると39本のツールスキーマが毎回プロンプトに注入される（~20,000 chars ≈ 5,000トークン/回）。ホワイトリスト化で74%削減可能。

利用可能なカテゴリ（`core/tools/` 配下のモジュール名）:
`aws_collector`, `call_human`, `chatwork`, `github`, `gmail`, `image_gen`, `local_llm`, `slack`, `transcribe`, `web_search`, `x_post`, `x_search`

```markdown
# cicchi（オーケストレーター）
## 外部ツール
- web_search: yes
- x_post: yes
- x_search: yes
- local_llm: yes   # LM Studio Qwen連携がある場合

# rue（リサーチャー）
## 外部ツール
- web_search: yes
- x_search: yes

# kuro（ライター）
## 外部ツール
- web_search: yes

# sora（ビジュアルディレクター）
## 外部ツール
- image_gen: yes
- web_search: yes
```

---

## Step 3: cronスケジュールの更新

`~/.animaworks/animas/<name>/cron.md` を確認・更新する。

**cicchi（オーケストレーター）の推奨スケジュール**:
```markdown
## 日次オーケストレーション（朝）
- schedule: 0 9 * * *
- 本日の投稿計画を立案し、kuroに指示する

## 日次レビュー（夜）
- schedule: 0 21 * * *
- 本日の投稿結果を振り返り、翌日の改善点をまとめる
```

**rue（リサーチャー）の推奨スケジュール**:
```markdown
## 週次トレンド更新
- schedule: 0 8 * * 1
- 週のはじめにトレンド調査を行い、今週のコンテンツ方向性をcicchiに報告する
```

---

## Step 4: モデル設定の確認

```bash
# 各animaのモデル設定を確認（status.jsonがconfig.jsonより優先）
for anima in cicchi rue kuro sora; do
  STATUS=~/.animaworks/animas/$anima/status.json
  echo -n "$anima: "
  if [ -f "$STATUS" ]; then
    python3 -c "import json; d=json.load(open('$STATUS')); print(d.get('model','(未設定)'))"
  else
    echo "(status.jsonなし)"
  fi
done
```

**注意**: `gemini/gemini-*` や安価すぎるモデルは出力品質が低い。
推奨: cicchi/rue/kuro → `claude-haiku-4-5-20251001` 以上、sora → 画像生成モデルは不要（fal.ai使用）

モデル変更が必要な場合:
```bash
# 例: rueのモデルをhaiku-4-5に変更
python3 -c "
import json
path = '$HOME/.animaworks/animas/rue/status.json'
d = json.load(open(path))
d['model'] = 'claude-haiku-4-5-20251001'
# geminiのcredentialが残っている場合は削除
d.pop('credential', None)
json.dump(d, open(path,'w'), ensure_ascii=False, indent=2)
print('更新完了')
"
```

---

## Step 5: 最終確認チェックリスト

```bash
# episodes が空であること
echo "episodes件数: $(find ~/.animaworks/animas -path '*/episodes/*.md' | wc -l | tr -d ' ')" # → 0

# vectordb が空であること
echo "vectordb .bin件数: $(find ~/.animaworks/animas -path '*/vectordb/*.bin' | wc -l | tr -d ' ')" # → 0

# index_meta.json がリセットされていること
for anima in cicchi rue kuro sora; do
  echo "$anima index_meta: $(cat ~/.animaworks/animas/$anima/index_meta.json)"
done  # → {} × 4

# task_queueにpending/blockedが残っていないこと
for anima in cicchi rue kuro sora; do
  count=$(python3 -c "
import json, sys
lines = open('$HOME/.animaworks/animas/$anima/state/task_queue.jsonl').readlines()
print(sum(1 for l in lines if l.strip() and json.loads(l).get('status') in ('pending','blocked','in_progress')))
" 2>/dev/null || echo 0)
  echo "$anima pending/blocked: $count"  # → 0
done

# knowledgeに旧テーマファイルが残っていないこと（目視確認）
for anima in cicchi rue kuro sora; do
  echo "=== $anima/knowledge ==="; ls ~/.animaworks/animas/$anima/knowledge/
done

# assetsに旧テーマ素材が残っていないこと（目視確認）
for anima in cicchi rue kuro sora; do
  echo "=== $anima/assets ==="; ls ~/.animaworks/animas/$anima/assets/ | grep -v "avatar_\|prompt.txt"
done

# x_post_log.mdが5件以内であること
wc -l ~/.animaworks/animas/cicchi/knowledge/x_post_log.md  # → ~10行程度

# permissions.mdのツールが絞られていること
for anima in cicchi rue kuro sora; do
  echo "=== $anima 外部ツール ==="; grep "yes\|no" ~/.animaworks/animas/$anima/permissions.md
done
```

---

## Step 6: サーバー再起動

```bash
launchctl kickstart -k gui/$(id -u)/com.animaworks.server
```

---

## Step 7: 初回動作確認

再起動後、次のHBサイクル（最大30分）でcicchiが新ミッションを認識しているか確認する。

確認方法:
1. パイプラインUIで cicchi の活動を見る
2. 旧ミッション（削除したキーワード）が出てきたら → Step 1 を再実施
3. 新ミッションに沿った行動が出たら → 完了
4. **委任イベント（`cicchi → rue/kuro 委任`）がパイプラインに表示されること**を確認する

---

## よくある問題と対処

| 症状 | 原因 | 対処 |
|------|------|------|
| 削除したはずの旧キーワードが再出現 | knowledge/assets/episodesの削除漏れ | Step 1-2〜1-3を最優先で確認。vectordbだけでなくknowledgeファイルそのものを削除 |
| Animaが12文字程度の短い返答しかしない | status.jsonが安価なモデルを参照している | Step 4でstatus.jsonを直接確認・修正 |
| タスクが自動実行される（承認前に投稿等） | background_tasksに旧タスクが残存 | Step 1-8の`rm -f`コマンドを確認 |
| パイプラインに委任イベントが表示されない | activity_logに`task_delegated`イベントがない | `core/tooling/handler_org.py`のログ出力を確認 |
| rueが旧テーマで調査を始める | injection.mdの専門領域に旧ミッション記述が残っている | Step 2-2を再確認 |
| トークン消費が多くてすぐレートリミットに当たる | `- all: yes`で不要なツールが大量注入されている | Step 2-3でpermissions.mdをホワイトリスト化 |
| Telegramで「OK」を送ってもキャンセルされる | `x_post_request_approval`ツール未登録 or injection.mdに承認フロー記述なし | Step 2-2のX投稿承認フローセクションを確認 |

---

## トークン消費の目安と削減ポイント

| 項目 | 削減前 | 削減後 | 手順 |
|------|--------|--------|------|
| ツールスキーマ（cicchi） | ~20,000 chars | ~5,000 chars | Step 2-3 |
| x_post_log（知識ファイル） | ~4,000 chars（14件） | ~600 chars（5件） | Step 1-4 |
| 空heartbeatのAPI呼び出し | 深夜14回分 × 4anima | 0回（スキップ） | コア実装済み |

---

## 補足: 新Animaを一から作る場合

既存animaの刷新ではなく新規作成の場合は `animaworks anima create` コマンドを使用する:

1. キャラクターシート（character_sheet.md）を1ファイルで作成
2. `animaworks anima create --from-md <パス>` を実行
3. サーバーのReconciliationが自動検出・起動

詳細は `animaworks-guide` スキルを参照。
