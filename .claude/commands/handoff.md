---
name: handoff
description: セッション引き継ぎファイルを作成する。knowledge_lint を自動実行し、結果をハンドオフに含める。
---

# ハンドオフ作成

セッション終了時の引き継ぎファイルを作成する。

---

## Step 1: Knowledge Lint 実行

以下のコマンドを実行し、結果を取得する:

```bash
uv run python scripts/knowledge_lint.py --json
```

JSON出力を変数として保持する。exit code 1（critical あり）でも続行すること。

---

## Step 2: 現在の状態を把握

以下を確認する:
1. `git status` で変更ファイル一覧を取得
2. `git diff --stat` で変更量を把握
3. `git log --oneline -5` で直近のコミットを確認

---

## Step 3: ハンドオフファイル作成

`.agent/handoff/YYYY-MM-DD-HHMM.md` を以下の構成で作成する（日時は現在時刻、JST）:

```markdown
# HANDOFF — YYYY-MM-DD HH:MM

## 使用ツール
Claude Code (使用モデル名)

---

## 今回のセッションで実施した内容
（セッション中に行った作業・修正・議論の要約をここに書く）

## 未完了・次回の確認ポイント
（次のセッションで対応すべき事項）

## 変更ファイル一覧
（git status / git diff の結果から主要なものを列挙）

## モデル構成
| anima | モデル | ロール |
|-------|--------|--------|
| cicchi | ... | X事業部オーケストレーター |
| rue | ... | ニッチ調査 |
| kuro | ... | コンテンツ制作 |
| sora | ... | ビジュアル生成 |
| hana | ... | エンゲージメント担当 |
| maru | ... | TikTok事業部リーダー |
| chiro | ... | トレンド調査 |
| tama | ... | カルーセル制作 |

---

## Knowledge Lint レポート
> knowledge_lint.py の実行結果。critical/warning の件数と主要な issue を記載する。

**サマリ**: critical N件, warning N件（全Mファイルスキャン）

### Critical Issues
（critical の issue を一覧で記載。件数が多い場合はカテゴリ別に集約してよい）

### Warning Issues
（warning があれば記載。なければ省略可）
```

### 注意事項
- **機密情報を書かない**: APIキー・トークン等は記載しない。「値は `.env` 参照」と書く
- Knowledge Lint の結果は**そのまま全件貼らない**。カテゴリ別に集約し、代表例を示す形にする
- criticalが0件の場合は「知識矛盾なし ✅」と1行書く

---

## Step 4: HANDOFF.md 更新

`.agent/handoff/HANDOFF.md` の内容を、Step 3 で作成したファイルの内容で**上書き**する。

---

## Step 5: ユーザーに報告

以下を報告する:

1. ハンドオフファイルのパス
2. Knowledge Lint のサマリ（critical/warning 件数）
3. **criticalが1件以上ある場合**: 主要なissueを簡潔に説明し、「対応が必要ですが、指示をお願いします」と伝える
4. **criticalが0件の場合**: 「知識矛盾なし」と報告

---

## Step 6: 持ち越し事項の確認

「未完了・次回の確認ポイント」に記載した事項をユーザーに提示し、次回セッションへの持ち込みを確認する。

- 各項目を箇条書きで列挙する
- 「次回に持ち越してよいですか？不要な項目があれば削除します」と確認する
- ユーザーが削除を指示した項目はハンドオフファイルから即座に削除し、HANDOFF.md を再同期する
- 承認された項目のみを次回に引き継ぐ

---

## 補足: Knowledge Lint カテゴリ一覧

| カテゴリ | 内容 |
|---------|------|
| `char_limit` | 文字数制限の不一致（280 vs 25000 等） |
| `tool_name` | 存在しないツール名の参照 |
| `format_rule` | 投稿形式の矛盾（4連投 vs 長文単一投稿） |
| `deprecated_term` | 廃止済み用語の残存 |
| `workflow` | ワークフロー役割割り当ての不整合 |
