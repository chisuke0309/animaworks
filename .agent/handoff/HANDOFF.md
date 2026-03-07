# HANDOFF - 2026-03-07

## 作業対象プロジェクト
AnimaWorks（/Users/chisuke/Projects/animaworks）

## 今日の作業まとめ

- [x] **sora（ビジュアルディレクター）エージェントの実装・登録**
  - injection.md / identity.md / cron.md / permissions.md 作成
  - パーソナルツール `tiktok_visual.py`（generate_tiktok_image / overlay_text_on_image / send_carousel_to_telegram）
  - `config.json` に登録（supervisor: cicchi）
  - `.env` に FAL_KEY・TELEGRAM_CHAT_ID を追記
  - cicchi の委任表に sora を追加
  - **identity.md が必要**であることを発見（ないと起動されない仕組み）

- [x] **4体のキャラクターリニューアル**
  - cicchi → **ちっち**（昭和風・人情味・32歳男性）
  - kuro → **くろ**（クールな今風・27歳男性）
  - rue → **ルー**（既存キャラ維持・日本語名のみ変更）
  - sora → **そら**（クールビューティー・22歳女性）

- [x] **キャラクターアセット全体再生成**
  - 全4体 × （全身立ち絵・バストアップ・7表情・ちびキャラ）を再生成
  - FAL_KEY（Fal Flux）で Step1〜3 を実行
  - 3Dモデルは MESHY_API_KEY 未設定のためスキップ

## チーム構成（現在）

```
ちっち / cicchi（マネージャー・昭和風30代男性）
├── ルー / rue（リサーチャー・知的な女性）
├── くろ / kuro（ライター・クールな若者男性）
└── そら / sora（ビジュアルディレクター・クールな女性）
     ├── generate_tiktok_image（fal.ai FLUX）
     ├── overlay_text_on_image（Pillow）
     └── send_carousel_to_telegram（Telegram）
```

## 既知の課題

| 課題 | 状態 |
|------|------|
| dispatch.py zen-saha ブランチ未マージ | 持ち越し |
| 3Dモデル未生成（MESHY_API_KEY なし） | 放置可 |
| cicchi のアバター画像（ANTHROPIC_API_KEY なし）→ FAL で生成済みに解消 | ✅ 解消 |
| slack_bolt 未インストール（Slack 未使用のため影響なし） | 放置可 |

## 次のセッションで最初にやること

1. ダッシュボードで新キャラクターの表示を確認
2. sora の実動確認（17:30 の自動カルーセル生成）
3. dispatch.py PR 作成（zen-saha → main）
Batch inference investigation concluded. User decided not to proceed.

## Bedrock利用とコスト課題について
* AWS Bedrock（Claude 3.5 Haiku/Sonnet）への移行検証を実施。
* 稼働検証において、ごく短期間の利用で11ドルの予期せぬ高額課金が発生。
* **原因分析:**
  * エージェントの自律ループ（思考→ツール実行→再思考）によりAPIコールが頻発するアーキテクチャであること。
  * LiteLLM経由のBedrock呼び出しにおいて、AnthropicAPIのようなプロンプトキャッシュ（Prompt Caching）が有効に機能しておらず、毎回履歴（数万トークン）をフルで送信し、従量課金対象になっている可能性が高い。
* **結論:** 現状のコンテキスト送信の仕組みでは、Bedrock（従量課金）は非常に割高となり不適合であると結論付けた。
* **今後の方針:** 近々ローカルLLM環境（Ollama等）の導入を予定。それまではこの仕組み（LLMによる自律エージェント機能）は一旦稼働停止とする方針となった。
