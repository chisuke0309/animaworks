# MEMORY.md — animaworks プロジェクト経験記録

---

## X事業部 運用終了（2026-05-01）

**決定**: ペットケアコンテンツのX自動投稿運用を終了。

**理由**: 約6週間稼働、フォロワー9名止まり。継続の費用対効果なしとchisuke判断。

**存続する資産（コードはすべて保持）**:
- 自動X投稿パイプライン（`core/tools/x_post.py`）
- ニッチ調査・ハッシュタグリサーチ（rue anima）
- コンテンツ生成テンプレート（kuro anima）
- 画像生成連携（sora anima）

**再開方法**:
```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.animaworks.server.plist
```

**停止方法（再停止時）**:
```bash
launchctl bootout gui/$(id -u)/com.animaworks.server
launchctl disable gui/$(id -u)/com.animaworks.server
```

→ 活用方法は別途検討予定（時期未定）

---

## TikTok事業部の運用モード: 人間ゲート付き稼働（2026-05-09 確定・継続）

**TikTok 事業部は「人間ゲート付き運用」**。Anima は制作と Telegram 配信までを担当し、TikTok への投稿は **chisuke が手動で行う**。Anima から TikTok への自動投稿は行わない。

これは新しいルールではなく、現状の運用そのもの。次セッション以降の Claude が「自動投稿に進めますか？」と誤って提案しないために明文化した。

**自動投稿に進める条件**（一つでも欠けていれば人間ゲート維持）:

- judge プロンプト改修（5/9実装）の効果が実 LLM テストで確認済み
- chiro の事実検証 protocol が実運用で 2週間以上同種事故ゼロ
- 06:30 自動スクレイピング復旧
- chisuke の最終確認で差し戻し率が 10% 以下に安定

**詳細**: `.agent/units/tiktok_unit.md` の「運用モード」セクション参照。

---

## tama 性能問題の真因と案E設計（2026-05-09 確定）

### 真因

tama の「性能問題」は Sonnet 4.6 の能力不足ではなく、**フロー設計の構造問題**:

1. **maru が judge の伝書鳩になっていた**: judge fail を3回受けても、suggestion をそのまま転送するだけで「なぜループするか」を分析しなかった（編集長機能不在）
2. **tama に「投稿物として完成しているか」を判断するステップがなかった**: 部品作りに集中し、テーマ整合・スライド間重複・ストーリー連続性を見ていない
3. **委任テンプレが過剰肥大化**: 30以上の制約を毎回再掲し、tama の認知資源を末端の細則に向けてしまっていた

### 案E実装内容（2026-05-09 12:00 reload）

- **maru/injection.md**: 編集長プロトコル追加（1回目は転送可・2回目以降は maru 自身の分析必須・3回目は強制エスカレ）
- **maru/injection.md**: 委任テンプレ整理ルール（手順書・knowledgeに既にあるルールは委任で再掲しない原則）
- **tama/knowledge/carousel_production_rules.md**: 制作後セルフレビュー3項目（テーマ整合・スライド間重複・ストーリー連続性）

### 効果検証ポイント

5/10 朝枠以降の cron で：

- maru が judge fail 2回目で suggestion 転送をやめて自分の分析を入れているか
- tama がテーマ整合チェックを通過しているか（製品名が overlay に登場するか）
- 委任メッセージが軽くなっているか

### 教訓

「LLMの能力不足」と判断する前に、フロー設計（誰が何を判断する責任を持つか・自己監査の限界・委任の表現出力）を見直すべき。Opus に格上げする判断は **設計を直してからの最後の手段**。

---

## システム特性: Role Contract 設計が「指示外の正しい行動」を生む（2026-05-09 観察）

**現象**: maru に対して「夕方枠スキップ＋tamaへの中止通知＋自分のknowledge更新」を inbox DM で指示したところ、maru は指示にない **chiro への自発的な事故共有** まで行った。

**maru の自発的行動内容**:

- chiro に「事実誤認の経緯＋新ルール（Anthropic公式ニュース引用時は出典URL確認必須）＋5/10朝枠向け調査依頼」を送信
- 自分の `knowledge/chiro-data-quality.md` を 16秒間で編集（ルール反映）

**なぜ起きたか**:
2026-05-06 に maru の `injection.md` に NEXUS スタイルの **Role Contract 構造**（Role / Specialty / Deliverables / Boundaries / DoD / Downstream / Escalation）を導入済み。「Downstream（部下への波及責任）」が明文化されていることで、エラーが起きたら downstream の chiro に共有する責務を maru が自分で判断して実行できた。

**含意**:

- 個別タスクの手順書を厚くするより、**役割と責務の枠（Role Contract）を明確にする方が、想定外の事態への対応が広がる**
- 「指示にないが正しい行動」を Anima が取れるかは、Role Contract の設計品質を測る一つの指標になる
- 横展開の候補: cicchi（X事業部）にも同様の Role Contract を入れているが、この種の自発行動が観察できれば設計の有効性がさらに裏付けられる

**初観察日**: 2026-05-09 11:09（draft_20260508_evening 事実誤認スキップ対応時）

---

## AnimaWorksサーバー管理

- **LaunchAgent**: `~/Library/LaunchAgents/com.animaworks.server.plist`
- **サービス名**: `com.animaworks.server`
- **再起動**: `launchctl kickstart -k gui/$(id -u)/com.animaworks.server`
- **現在の状態**: 停止・自動起動無効（2026-05-01時点）

---

## 🚨 AnimaWorks の実際の認証経路（2026-05-15 判明・重要）

### 事実

**AnimaWorks の各 Anima は、`config.json` の API キーではなく、chisuke の Claude Max プランの OAuth セッションで動いている。**

### 経路

```
AnimaWorks (Python)
  ↓ claude-agent-sdk (A1 モード)
    ↓ SubprocessCLITransport で subprocess 起動
      claude CLI (/opt/homebrew/bin/claude)
        ↓ OAuth 認証（~/.claude/sessions）
          ↓ chisuke の Max プランで API 接続
```

### 検証根拠

- `config.json` の `credentials.anthropic.api_key` (`sk-ant-api03-khc...9XMgAA`) で直接 `/v1/messages` を叩くと **HTTP 401**（無効）
- それでも AnimaWorks のサーバー（PID 902）と全 Anima supervisor は稼働中、activity_log に LLM 応答も継続記録
- `claude-agent-sdk` の内部実装が `SubprocessCLITransport` で `claude` CLI を起動する設計
- `~/.claude/sessions` に Max プランの OAuth セッション保存

### Anthropic Console の API キー（参考）

| ラベル | 末尾 | 用途 |
|---|---|---|
| mail | `5wAA` | 別用途 (USD 0.01) |
| Academy | `JQAA` | 別用途 (USD 0.00) |
| animaworks | `4QAA` | **AnimaWorks 用ではない**（実際は Max OAuth で動いている） |

config.json の `khc...9XMgAA` は **どのキーとも一致しない**（おそらく過去に削除されたキー）。

### 6/15 以降のリスク（Anthropic「プログラマティック使用クレジット」開始）

**6/15 以降、AnimaWorks は Max プランの新「プログラマティック使用クレジット」枠の対象になる可能性が極めて高い。**

- Max 20x プランのクレジット枠は **$200/月・繰越不可・月末で消える**
- AnimaWorks の Anima 8体が毎時 Heartbeat / Inbox / Cron を回す消費量で $200/月は **確実に足りない**
- **6/15 を境に AnimaWorks が動かなくなる可能性が極めて高い**

### 対応方針

- **TikTok 事業部は実験終了で停止**（2026-05-15 chisuke 判断、運用検証は完了）
- **X 事業部は継続稼働**（実地計測の対象）
- **6/15 以降に実地で消費量を計測**してから本格対策を決める

### 検討中の対応案（6/15 以降）

| 案 | 内容 | 影響 |
|---|---|---|
| A | A1F モード強制（Anthropic SDK 直接・API キー認証）に切り替え | コスト見える化＋クレジット制限回避、ただし USD 課金が明示的に発生 |
| B | Anima 稼働を絞ってクレジット内に収める | 機能削減 |
| C | LiteLLM 経由で別プロバイダ（Gemini など）に移す | API 互換性検証必要 |
