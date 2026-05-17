# AnimaWorks Eval Harness (MVP)

Promptfoo を使った prompt 回帰テスト。2026-05-08 chisuke 介入で発覚した3類型の再発防止用。

## 何をテストしているか

| テスト | ファイル | 検出する失敗 |
| --- | --- | --- |
| chiro 事実紐付け | `tests/chiro_fact_check.yaml` | 別記事の主張を1本に合体（Opus4.7+SpaceXの誤紐付け）／URL捏造／要約の汎用語化 |
| tama CTA-本体整合 | `tests/tama_cta_alignment.yaml` | スライド5に「番号でコメント」と書いて本体に①②③が無い |
| tama 宙吊り表現 | `tests/tama_dangling_phrase.yaml` | 「見返して」「保存して」だけでスライドを終わらせる／保存動機不明 |
| tama 文体rubric | `tests/tama_rubric_quality.yaml` | 主述の不自然・比喩の不成立・フック弱さ・ベネフィット主語の欠落（5/8「仕事の道具を更新した」事件で発覚） |

なお tama 文体rubric と同等のチェックは **本番運用パスでも `tiktok_judge_overlay_texts` ツールが maru の Step 4 品質チェック 7番として呼ばれる**（`maru/injection.md` 参照）。eval は CI レイヤーで独立に検証する役割。

## 走らせ方

```bash
cd ~/Projects/animaworks/eval
export $(grep ^ANTHROPIC_API_KEY ../.env | xargs)  # .envから読み込み

# chiro 用テスト
npx -y promptfoo eval -c chiro.config.yaml

# tama 用テスト
npx -y promptfoo eval -c tama.config.yaml

# レポート閲覧（直近の eval 結果）
npx -y promptfoo view
```

config を chiro/tama で分割しているのは、prompt × test の cross-product を避けるため（promptfoo は同一 config 内では全 prompts × 全 tests を実行する）。

## 設計メモ

- provider は `claude-sonnet-4-6` をデフォルトに（コスト・速度バランス）
- 各 assertion は `javascript` で書き、失敗時のメッセージに「5/8失敗パターン」と明示している（後で誰が見ても回帰の意図が分かるように）
- prompt は実際の Anima injection.md ではなく **タスク再現用の最小プロンプト**。Anima 完全再現は別フェーズ（providers/animaworks-anima.py を後で作る）

## 増やし方

新しい失敗類型を見つけたら：

1. `tests/<short-name>.yaml` に新しいテストケースを追加（既存ファイルを参考に）
2. `promptfooconfig.yaml` の `tests:` リストに `file://tests/<short-name>.yaml` を足す
3. 新しい prompt が必要なら `prompts/` に追加
4. `npx promptfoo eval` で確認

## 既知の制約

- Anima の状態（vectordb / activity_log / 過去メッセージ）を再現していない。「環境込みの挙動」を見たいときは別レイヤーが必要
- 確率的に通る/落ちるテストは `temperature: 0.2` で抑えているが、完全決定的ではない
