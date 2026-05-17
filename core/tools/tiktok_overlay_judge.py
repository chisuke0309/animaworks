# AnimaWorks - Digital Anima Framework
# Copyright (C) 2026 AnimaWorks Authors
# SPDX-License-Identifier: Apache-2.0

"""TikTok overlay_texts judge — LLM-as-judge による文体・主述・比喩のチェック.

maru の Step 4 品質チェックに「文字数・行数・存在チェック」しか無く、
日本語としての自然さ・主述の所有関係・比喩の成立を見ていなかった問題への対応
（2026-05-08 chisuke 指摘）。

別 LLM に 5 項目で採点させ、いずれか 2 点以下なら不合格を返す。
maru は不合格ならtamaへ差し戻すことで、chisuke のレビューに到達する前に止める。
"""

from __future__ import annotations

import json
import time
from typing import Any

from core.tools._base import get_credential, logger

DEFAULT_JUDGE_MODEL = "claude-opus-4-7"  # 採点はOpusで厳しく見る
DEFAULT_MAX_TOKENS = 2048

JUDGE_SYSTEM_PROMPT = """\
あなたは TikTok カルーセル投稿の overlay_texts（各スライドに焼き込むテキスト 5 枚）の品質を採点する厳格な編集者です。

視聴者は TikTok を流し見する一般人で、各スライドを 3 秒以下で判断します。
あなたは tama（制作担当）が出した overlay_texts を読み、以下の 5 項目で各 5 点満点採点してください。

## 採点項目（各5点満点）

1. **単体完結性** — 各スライドが、前後やキャプション無しで「何の話か」が3秒で読み取れる
2. **主述の自然さ** — 主語・目的語・所有関係が日本語として自然（「AI3社が仕事の道具を更新した」のように所有者が曖昧な比喩は減点）
3. **比喩の成立** — 比喩を使う場合、視聴者の大半が同じ意味で受け取れる範囲（深読みしないと意味が通らない比喩は減点）
4. **フックの前のめり度** — 1枚目が「続きを見たい」と思わせる作りか（過去の事実報告だけ、抽象語の羅列は減点）
5. **ベネフィット主語** — 視聴者の利益・関心が主語になっているか（製品名・企業名だけが主語は減点）

## 採点基準

- 5点: 全く違和感なく、視聴者目線で完璧に通る
- 4点: 軽微な違和感はあるが、十分通る
- 3点: 違和感はあるが、意図は通る
- 2点: 主述や比喩に問題があり、再検討すべき
- 1点: 意味が通らない・誤解を生む

## 合否判定（厳格モード）

以下のいずれかに該当したら fail：

- **いずれか1項目でも 3 点以下**（3点ジャストもfail。違和感を感じたなら通さない）
- **5 項目の平均が 4.0 未満**
- **issues 配列に1件でも違和感を記載した場合**（言葉で問題を表現できた時点で「気になるレベル」のため通さない）

逆に、全項目4点以上 かつ issues が空配列のときのみ pass。

採点は遠慮せず、視聴者の違和感を最優先に厳しく採点すること。tama に差し戻して書き直しさせるほうが、視聴者に違和感を与えるより遥かに安い。

## 【重要】suggestion における事実主張の保持原則【2026-05-09追加】

過去事故（5/9夕方枠）：judge が suggestion で「使える量が2倍」を「記憶量が2倍」に書き換え、tama がそのまま採用 → 事実誤認のまま納品寸前に。

**suggestion は「文体・構造・主述の自然さ」だけを直し、事実主張部分は触らないこと。**

具体的に：

- **触ってよい**: 改行位置、語順、助詞、敬体/常体、抽象語→具体語、冗長語の削除、視聴者目線への言い換え
- **触ってはいけない**:
  - 固有名詞（Claude / ChatGPT / Gemini / OpenAI / Anthropic / Google など）
  - 数値（2倍、半減、52.5%、5時間、1万行 など）
  - 対象語（「利用枠」「レート制限」「記憶量」「コンテキスト」「メモリ」「精度」「速度」など、何が変わったかを示す名詞）
  - 出典・主体（誰が・何を・どれだけ）

**判断に迷うケース（重要）**:

- 元の overlay に「使える量が2倍」のように対象が**曖昧**な語があった場合、それを別の名詞に**置き換えてはいけない**。
- 代わりに issues で「対象が曖昧。chiro/tama に確認が必要」と指摘し、suggestion は**空欄**にするか「[要確認] 元の対象が曖昧」と書く。
- 「容量」「機能」「性能」のような曖昧名詞も同様。確認できないなら suggestion に勝手な解釈を入れない。

**禁止例（やってはいけない置換）**:
- ❌ 「使える量が2倍」→「記憶量が2倍」（"使える量"を勝手に"記憶量"と解釈）
- ❌ 「Claudeの容量が拡大」→「Claudeのコンテキストが拡大」（"容量"を"コンテキスト"と決めつけ）
- ❌ 「精度向上」→「ハルシネーション50%減」（数値を発明）

**OK例（やってよい修正）**:
- ✅ 「Claudeの利用枠が2倍に」→「Claudeの利用枠が2倍に拡大」（"拡大"を補うのは構文補完）
- ✅ 「使える量が2倍」→ suggestion 空欄 + issues「対象が曖昧（"使える量"の対象が利用枠かコンテキストか不明）。tama/chiro に確認が必要」

## 【重要】事実主張があるのに出典が無いと検出された場合

入力に `factual_claims` または `source_urls` が含まれていない / 空であり、かつ overlay_texts に固有名詞・数値・日付が含まれているスライドがある場合、issues に以下を必ず追加すること：

- 「スライドN: 事実主張あり（[該当語]）。出典 URL が judge に渡されていないため、事実検証が外部で必要」

## 出力フォーマット（必須・JSON のみ）

```json
{
  "scores": {
    "single_slide_clarity": <int 1-5>,
    "subject_object_naturalness": <int 1-5>,
    "metaphor_validity": <int 1-5>,
    "hook_strength": <int 1-5>,
    "viewer_benefit_subject": <int 1-5>
  },
  "verdict": "pass" | "fail",
  "issues": [
    "スライドN: 具体的な問題と理由（200字以内）",
    ...
  ],
  "suggestions": [
    "スライドN: 推奨修正案（30字以内）。事実主張部分は変えないこと。判断に迷うなら空欄または『[要確認] 理由』",
    ...
  ]
}
```

issues と suggestions は問題があるスライドのみ記載。問題が無いなら空配列。
JSON 以外の説明文は一切書かないこと。
"""


def _build_user_message(
    overlay_texts: list[str],
    topic: str | None = None,
    factual_claims: list[str] | None = None,
    source_urls: list[str] | None = None,
) -> str:
    parts = []
    if topic:
        parts.append(f"## テーマ\n{topic}\n")
    if factual_claims:
        parts.append(
            "## chiro が確認した事実主張（これらの主張は overlay_texts でそのまま保持されるべき）"
        )
        for c in factual_claims:
            parts.append(f"- {c}")
    if source_urls:
        parts.append("## chiro が確認した出典 URL")
        for u in source_urls:
            parts.append(f"- {u}")
    if not factual_claims and not source_urls:
        parts.append(
            "## 注意：事実主張・出典 URL が judge に渡されていない\n"
            "overlay_texts に固有名詞・数値・日付が含まれるスライドがあれば、"
            "issues に「事実主張あり・出典未提供」を追加すること。"
        )
    parts.append("## overlay_texts（5枚）")
    for i, t in enumerate(overlay_texts, 1):
        parts.append(f"### スライド{i}\n{t}")
    parts.append("\n上記を採点フォーマットの JSON で返してください。")
    return "\n\n".join(parts)


def judge_overlay_texts(
    overlay_texts: list[str],
    topic: str | None = None,
    factual_claims: list[str] | None = None,
    source_urls: list[str] | None = None,
    model: str = DEFAULT_JUDGE_MODEL,
) -> dict[str, Any]:
    """別 LLM に overlay_texts を5項目採点させる。

    Args:
        overlay_texts: 5 要素の文字列配列。改行は \\n（バックスラッシュ+n）でも実改行でも可
        topic: 投稿テーマ（オプション、判定の文脈になる）
        model: 採点用モデル

    Returns:
        {
          "success": bool,
          "verdict": "pass" | "fail",
          "scores": {...},
          "issues": [...],
          "suggestions": [...],
          "raw": str  (LLM の生レスポンス、デバッグ用)
        }
    """
    if not isinstance(overlay_texts, list) or len(overlay_texts) != 5:
        return {
            "success": False,
            "verdict": "fail",
            "error": f"overlay_texts は 5 要素必要（受領: {len(overlay_texts) if isinstance(overlay_texts, list) else 'not-list'}）",
        }

    try:
        import anthropic  # type: ignore[import-not-found]
    except ImportError:
        return {
            "success": False,
            "verdict": "fail",
            "error": "anthropic SDK not installed",
        }

    api_key = get_credential(
        credential_name="anthropic",
        tool_name="tiktok_overlay_judge",
        env_var="ANTHROPIC_API_KEY",
    )
    client = anthropic.Anthropic(api_key=api_key)

    user_msg = _build_user_message(
        overlay_texts,
        topic=topic,
        factual_claims=factual_claims,
        source_urls=source_urls,
    )
    logger.info("tiktok_overlay_judge: calling %s", model)
    t0 = time.time()
    resp = client.messages.create(
        model=model,
        max_tokens=DEFAULT_MAX_TOKENS,
        system=JUDGE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    elapsed = time.time() - t0

    raw = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
    logger.info("tiktok_overlay_judge: %d chars in %.1fs", len(raw), elapsed)

    # JSON 抽出（マークダウンコードフェンス対応）
    cleaned = raw
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
    cleaned = cleaned.strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "verdict": "fail",
            "error": f"judge LLM の出力が JSON として不正: {e}",
            "raw": raw,
        }

    # 防衛的な verdict 補正（LLM の自己判定より厳しく、システム側で再評価する）
    scores = parsed.get("scores", {})
    issues = parsed.get("issues", [])
    score_values = [v for v in scores.values() if isinstance(v, (int, float))]
    has_low = any(v <= 3 for v in score_values)  # 3点ジャストでもfail
    avg = sum(score_values) / len(score_values) if score_values else 0
    has_issues = len(issues) > 0

    if has_low or avg < 4.0 or has_issues:
        verdict = "fail"
        fail_reasons = []
        if has_low:
            fail_reasons.append("3点以下の項目あり")
        if avg < 4.0:
            fail_reasons.append(f"平均{avg:.1f}点 < 4.0")
        if has_issues:
            fail_reasons.append(f"issues {len(issues)}件")
    else:
        verdict = "pass"
        fail_reasons = []

    return {
        "success": True,
        "verdict": verdict,
        "scores": scores,
        "issues": issues,
        "suggestions": parsed.get("suggestions", []),
        "fail_reasons": fail_reasons,
        "average_score": round(avg, 2),
        "model": model,
        "elapsed_sec": round(elapsed, 1),
    }


# ── Tool Schemas ──────────────────────────────────────────


def get_tool_schemas() -> list[dict]:
    return [
        {
            "name": "tiktok_judge_overlay_texts",
            "description": (
                "TikTokカルーセルのoverlay_texts（5スライド分のテキスト）を別LLMで採点する。"
                "5項目（単体完結性・主述の自然さ・比喩の成立・フック強度・ベネフィット主語）を5点満点で採点し、"
                "いずれか2点以下なら fail を返す。maru の Step 4 品質チェックの最終関門として呼ぶこと。"
                "fail の場合は issues / suggestions を読んで tama に差し戻すこと。"
                "事実主張（固有名詞・数値・日付）を含む overlay の場合は、必ず factual_claims と "
                "source_urls を渡すこと。渡されていれば judge は suggestion で対象語を勝手に書き換えない。"
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "overlay_texts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "5枚分のoverlay_text。draftJSONの overlay_texts をそのまま渡す",
                    },
                    "topic": {
                        "type": "string",
                        "description": "投稿テーマ（オプション、判定の文脈になる）",
                    },
                    "factual_claims": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "chiro が確認した事実主張のリスト（任意）。"
                            "例: ['Claude Code の5時間レート制限が2倍に', "
                            "'Gemini Deep Research Max がリサーチ自動化機能を追加']。"
                            "judge はこれらの主張を overlay_texts でそのまま保持されているか確認し、"
                            "suggestion でも勝手に書き換えない。"
                        ),
                    },
                    "source_urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "chiro が確認した出典 URL リスト（任意）。"
                            "例: ['https://www.anthropic.com/news/higher-limits-spacex']。"
                            "judge は出典が渡されていれば事実検証根拠ありとみなす。"
                            "渡されていない場合は issues に出典未提供を追記する。"
                        ),
                    },
                },
                "required": ["overlay_texts"],
            },
        },
    ]


# ── Dispatch ──────────────────────────────────────────────


def dispatch(name: str, args: dict[str, Any]) -> Any:
    args.pop("anima_dir", None)
    if name == "tiktok_judge_overlay_texts":
        return judge_overlay_texts(
            overlay_texts=args["overlay_texts"],
            topic=args.get("topic"),
            factual_claims=args.get("factual_claims"),
            source_urls=args.get("source_urls"),
        )
    raise ValueError(f"Unknown tool: {name}")
