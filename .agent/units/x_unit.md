---
unit: x
updated: 2026-05-17
status: 業務AI体制（yomi Eval エージェント追加・5/17 morning投稿成功・evening 17:00 cron待機中）
---

# X事業部

## 🎉 2026-05-08 業務AI 体制 第1号投稿 公開成功

**5/6 に approved にしていた投稿を手動で発射**。サーバー停止中だったため5/6 17:00 cron は発火せず、本日（5/8）cicchi 事業部 5体起動後に `execute_pending_posts(slot='evening')` を直接呼んで発射。

- ID: `20260506T131722_evening`
- Tweet ID: `2052565477311087077`
- URL: <https://x.com/i/web/status/2052565477311087077>
- 画像表示: ✅ 本番環境でもFLUX背景＋Pillowオーバーレイが綺麗に表示された（chisuke確認済み）
- 品質スコア: 9.3/10
- pending JSON は発射成功時に自動削除済み

**cicchi 事業部 5体は本セッションで `enabled: true` 化＋起動**: 以後は cron による自動運用フェーズに入る。

## 🔄 2026-05-06 ジャンル転換 完了

**判断**: 旧体制（ペット・グルーミング情報、6週間でフォロワー9名）を完全終了し、屋号 trinitydox と整合する **業務AI / AI活用 / 業務改善** ジャンルへ全面転換。
あわせて NEXUS スタイルの **Role Contract 構造**（先日 maru で導入したもの）を cicchi 事業部 5 体に展開。
さらに既存リポジトリ `~/Projects/ai-research-hub/`（毎朝6:48に Obsidian Vault に5ソースを保存）を rue の一次ソースに位置付け、`topic_selection_criteria.md`（4層スコアリング）で投稿ネタ選定の透明性を確保。

---

## 現在の戦略（業務AI 体制）

### ターゲット
PM / DX推進担当 / 経営層 / 事業部長 / コンサルタント / SaaS担当

### 投稿ジャンル A〜E

| 記号 | ジャンル | 想定頻度 |
|------|---------|---------|
| A | 業務改善ケーススタディ | 週1〜2 |
| B | AIツール実務レビュー（Claude / Gemini / NotebookLM 等） | 週1 |
| C | PM × AI 実務（chisuke 本業ネタ・抽象化必須） | 週1〜2 |
| D | AI業界ニュースの実務翻訳 | 週2〜3 |
| E | プロンプト/Skill 公開 | 隔週〜月1 |

### 禁止テーマ（5項目を全 anima Boundaries に明示）
- AI副業・稼ぎ方系
- ペット・健康情報（旧体制の残骸）
- クライアント固有情報（抽象化レベル: 「ある製造業のデータ分析PJで…」まで）
- Anthropic Partner Network 公式発表（指示があるまで）
- AGI / シンギュラリティ煽り系

### 収益動線
trinitydox サイト誘導 → PMO/DX 案件相談（KPIに「サイト誘導数」を新設）

---

## KPI（業務AI 体制で再校正）

| 指標 | 現在 | 1ヶ月後 | 2ヶ月後 | 3ヶ月後 |
|------|------|---------|---------|--------|
| Xフォロワー数 | 9（5/14時点・2週間横ばい） | 50 | 200 | 500 |
| エンゲージメント率 | 5/9〜5/14 実測: 平均 imp 17 / like 0.7 / RT 0（5/14 計測復活） | 2% | 3% | 3%以上 |
| trinitydox サイト誘導数（週次） | 0 | 5 | 20 | 50 |

---

## Anima稼働状況

| Anima | ロール | 状態 |
|-------|--------|------|
| cicchi | X Division Lead（オーケストレーター） | 🟢 稼働中（2026-05-08 起動） |
| rue | X Division Researcher | 🟢 稼働中（2026-05-08 起動） |
| kuro | X Division Copywriter | 🟢 稼働中（2026-05-08 起動） |
| sora | X Division Visual Director | 🟢 稼働中（2026-05-08 起動） |
| hana | X Division Engagement Officer | 🟢 稼働中（2026-05-08 起動） |
| yomi | X Division Eval Agent（投稿品質審査） | 🟢 稼働中（2026-05-17 起動・CrowdWorks担当から転換） |

---

## 次のアクション

1. **5/17 evening 投稿確認**（17:00 cron 発火後）: `tweet_id` が `pending_posts/20260516T214945_evening.json` に書き込まれているか確認。画像 `~/.animaworks/tmp/x_image_20260517_evening.png` が添付されているか X タイムラインで目視確認。
2. **yomi Eval 初稼働の観察**（次回 21:00 cron 以降）: kuro から yomi への Eval 依頼 DM が yomi の activity_log に残るか確認。pass/fail 判定が正しく機能するかを確認。差し戻し→再提出→x_post_save_pending の一連フローを追う。
3. **6/15 以降の API 認証切り替え**: AnimaWorks は現在 Max OAuth で動作。6/15 以降に programmatic credits ($200/月) が適用され予算超過で止まる可能性あり。実地計測してから対策を決定予定。

---

## メモ・教訓

- **記憶クリーンアップは必須だった**: ジャンル転換時に knowledge ファイルを消すだけでは不足。`episodes/`・`vectordb/`・`activity_log/`・`state/conversation.json` が search_memory のソースになっており、過去のペット文脈が逆流するリスクがあった。MEMORY.md「全Animaクリーンアップ手順」を実施して解消。
- **Role Contract は cicchi 事業部全員に展開して問題なかった**: maru で実証済みの構造を5体すべてにコピー&カスタマイズ。knowledge_lint critical 0 / warning 0 で完了。
- **削除した knowledge は 約100本**: ペット運用記録（niche*.md、archive/、週次戦略履歴等）。フレームワーク部分は `genre_map.md` `weekly_strategy.md` に再構築。
- **保持した技術記録**: `image_posting_workflow.md`（OAuth1 認証バグ修正）、`x_account_suspension.md`（凍結対応）、`x_api_credential_fix.md`（API認証）— インフラノウハウは業務AI 体制でも有用。
- **ai-research-hub を一次ソースに位置付け**: 既存リポジトリ `~/Projects/ai-research-hub/`（毎朝6:00 launchd・6:48に5ソースを Obsidian Vault に保存）を rue の最優先情報源にした。ハルシネーション抑制 + ゼロから検索する負荷軽減。
- **使えなかった調査ツール**: yt-dlp（YouTube 署名チャレンジ未対応で 429）と Reddit JSON（403 Blocked）は injection から削除。bird CLI / Exa / Jina Reader / mcporter / web_search は完全動作確認済み。
- **投稿ネタ選定基準を明文化**: `topic_selection_criteria.md` に4層スコアリング（必須フィルター → 5軸×5点 → ジャンル偏り回避 → 最終判断）。15点以上で投稿候補。なぜそのネタを選んだかが報告に必ず残る。
- **phantom blocker + scheduled_for 修正済み**（2026-05-16 commit `815d7b99`）: `core/tools/x_post.py` に `_extract_blocker_id()` 追加。`execute_pending_posts` が blocker ファイル消失を検知して `gate=auto_approved` に自動昇格するロジック追加。`save_pending_post` に `scheduled_for` フィールド追加し conflict 検出を同日の slot のみに限定。`server/routes/approvals.py` の `approve_post` も gate を auto_approved に更新するよう修正。旧ファイル（`scheduled_for` なし）は conservative 扱い（conflict 判定される）のため、修正後も旧ファイルが残っている間は phantom blocker が発生し得る点に注意。
- **画像はストック使い回し + Pillow キャプション合成に変更**（2026-05-15）: FLUX は毎回課金されるため廃止。`~/.animaworks/assets/x_images/genre_A〜E/` に GPT Image 生成画像を各2枚格納済み。sora がジャンル別フォルダからランダム選択 → Pillow でキャプション（15〜25文字）をオーバーレイ → tmp/ に出力する。FLUX / `generate_image.py` は今後X投稿では呼ばない。
- **yomi を X投稿 Eval エージェントに転換**（2026-05-17）: 旧役割（CrowdWorks案件スカウト）を完全上書き。`identity.md` / `injection.md` / `cron.md` / `status.json` 全て書き換え。`cicchi/cron.md` の 09:00・21:00 タスクに Step 4（yomi Eval 依頼）と Step 4b（pass/fail分岐）を追加。5軸ルーブリック（x-post-evaluator Skill 参照）で採点 → pass なら x_post_save_pending / fail なら差し戻し最大2回 / 3回目は call_human。
- **x-post-evaluator Skill 作成済み**（2026-05-17）: `~/trinitydox-standards/skills/x-post-evaluator/SKILL.md` に5軸（hook_strength / personalization / information_density / structure_flow / cta_naturalness）の採点ルーブリックと JSON 出力フォーマットを定義。`sync-skills.sh` 実行済みで `~/.claude/skills/x-post-evaluator` にシンボリックリンク済み。
- **キャプションは kuro が作成**: 投稿テキストの核心を 15〜25 文字・体言止め or 短い断言形でまとめる。sora への委任メッセージに含めて渡す。
- **画像へのテキストオーバーレイは2段階が定石**: FLUX に日本語を直接書かせると文字化け確実。背景生成 → Pillow で日本語オーバーレイ（半透明黒の暗幕＋白文字）が綺麗に出る。`/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc` 使用。
- **fal_client は miniforge 環境にしか入っていない**: `.venv/bin/python` ではなく `/opt/homebrew/Caskroom/miniforge/base/bin/python` で実行する必要あり（venv は miniforge へのシンボリックリンクだが site-packages を共有していない様子）。
- **承認 API は `/api/approvals/posts/{id}/approve`**: prefix が `/api` なので `/approvals/...` だと 405。openapi.json で確認可能。
- **save_pending は同 slot に approved が残っていると新規を強制 pending 化**: queue backup 防止の安全装置。古い approved を削除してから新規を承認すれば良い。今回は旧体制（ペット）の `20260430T213350_evening` `20260430T211122_morning` を削除。
- **手動発射は `execute_pending_posts(slot, anima_dir)` を直接呼ぶ**: API には手動発射エンドポイントなし。`/opt/homebrew/Caskroom/miniforge/base/bin/python -c` で `from core.tools.x_post import execute_pending_posts` を import → slot を指定して呼ぶ。成功すると pending JSON は自動削除される。
- **Animaの起動は API で2段階**: `POST /api/animas/{name}/enable`（status.json.enabled を true に） → `POST /api/animas/{name}/start`（プロセス起動）。supervisor を先に起動するのが安全。
- **launchd `com.animaworks.server` が動いていても Anima プロセスは別**: サーバー稼働 ≠ 全 Anima 稼働。各 Anima の status.json.enabled と /api/animas のステータスで個別に確認が必要。
- **PDCA テンプレだけでは自己改善が起きない構造的理由**（2026-05-12 観察）: cicchi の HB は Observe→Plan→Execute→Verify→Reflect と PDCA を内蔵していたが、フォロワー1週間9人停滞でも「文字数を疑う」「他アカウントを見る」が一度も自発的に出なかった。原因は3つ — (1) Verify が「先週比改善したか」しか問わず根本前提を疑う設問が無い、(2) Reflect が任意・基準なしで「順調」と書きがち、(3) ベンチマーク（外部参照）の経路が無い。対策: 停滞時の Doubt フェーズを HB テンプレに強制挿入（5/12 実装）。
- **新フェーズヘッダ追加時は必ず `_RE_HB_PHASE_HEADER` regex 拡張が必要**（2026-05-12 実装）: 拡張しないと Doubt セクションの全文が episodes → RAG → 翌日プロンプトへ自己増殖するフィードバックループが発動する。今回は `core/_anima_heartbeat.py` L60/L69 に `Doubt` を追加して対処。AGENTS.md L322 の警告事項。
- **cron 定義はあるのに `type: command` cron が発火していない可能性**（要調査）: cicchi/cron.md の `x_post_update_engagement`（22:00）と `blackboard_update_org_status`（7時/21時）が実行ログに残っていない。cicchi 自身は「cron が無い」と認識していた → 自分の cron.md を読んでいない or `type: command` パスに別の不具合。
- **`update_engagement` の列インデックスバグ**（2026-05-14 修正）: `x_post_log.md` に「ジャンル」列が追加され9列構造になっていたのに、`core/tools/x_post.py` の `update_engagement` は旧8列構造（cols[3]=tweet_id 前提）のままだった。結果 cols[3] が「トピック要約」テキストになり isdigit() が常に False → 全行スキップ → 「All metrics up to date」を誤返却し続けていた。tweet_id 判定・"—" 検出・書き戻し列すべてを +1 シフトして修正（commit `45fc9708`）。教訓: テーブル列を追加するときは関連ツールも一緒に追跡する必要があり、インデックスではなく列名で引く設計が将来の追加に強い（今回はchisuke指示で最小修正を選択）。
- **hana のリプライ・引用「API権限制限」は誤認識だった**（2026-05-14 確定）: 過去「API信頼スコアが上がれば復帰」と理解していたが、X規約上の迷惑行為検知が真因。信頼スコアでは解禁されない（規約違反行為そのもの）。chisuke 直命で永久禁止確定。hana の `injection.md` / `knowledge/x_api_permissions_status.md` / `knowledge/engagement_targets.md` 全てに「永久禁止」を明文化、`state/task_queue.jsonl` に chisuke 直命タスク `ebcd29eb6f84` を追加。`x_reply` / `x_quote` は永久に呼び出さない。cicchi 経由の指示でも上書き不可（chisuke 直命優先）。
- **エンゲージメント計測 cron 不発の真因はおそらく PC 停止**（2026-05-14 推察）: chisuke 指摘どおり、launchd は PC スリープ中は走らない。3日間ゼロ発火は cron 自体の不具合ではなく稼働時間の問題と見られる。ツール側バグ修正と合わせて様子見。
- **キュー詰まり防止 = 安全装置として正常動作**（2026-05-14 確認）: 同スロットに approved が既にある状態で新規 auto_approved を生成すると、後者は `gate_reason: 承認済み投稿が残存…キュー詰まり防止のため人間レビュー待ちに変更` で pending に降格される（commit `adad38f2` の安全装置）。今回は cicchi から chisuke にレビュー依頼 → 「削除」判断で 5/15 evening (E型 score 8.8) と 5/16 morning (A型 score 9.0) の2件を削除し x_post_log.md からも除去。安全装置自体は正しく動いており、運用面で「自動裁定 vs 人間レビュー」のしきい値設計を cicchi 提案待ち。

---

## 旧体制の参考記録（ペット・グルーミング 2026-03 〜 2026-05-02）

- 稼働期間: 約6週間
- 最終フォロワー: 9名
- 技術的教訓:
  - X API 401 の真因: `x_post_log.md` の `—`（全角ダッシュ）vs `"-"` ミスマッチ（commit: 1a0e7245）
  - pending queue 詰まり: 同slot に approved が既にある場合の処理（commit: adad38f2）
  - フォロワー増加の壁: 短文・感情フック・画像添付施策を試したが伸びず → ジャンル自体の問題と判断
