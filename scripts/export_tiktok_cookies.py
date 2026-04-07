# AnimaWorks - Digital Anima Framework
# Copyright (C) 2026 AnimaWorks Authors
# SPDX-License-Identifier: Apache-2.0

"""TikTok Studio login — persistent browser profile.

Opens a visible Chromium with a persistent profile. User logs into
TikTok Studio (Google OAuth OK). The session is saved in the profile
directory and reused by subsequent headless scraper runs.

Usage:
    uv run python scripts/export_tiktok_cookies.py

Profile is stored at: ~/.animaworks/credentials/tiktok_profile/
"""
from __future__ import annotations

import sys
from pathlib import Path

PROFILE_DIR = Path.home() / ".animaworks" / "credentials" / "tiktok_profile"
TIKTOK_STUDIO_URL = "https://www.tiktok.com/tiktokstudio/content"


def main() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright未インストール: pip install playwright && playwright install chromium")
        sys.exit(1)

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            channel="chrome",  # システムのChromeを使用（Chromiumだとgoogle認証拒否される）
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1280, "height": 900},
            locale="ja-JP",
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(TIKTOK_STUDIO_URL)

        print("=" * 60)
        print("ブラウザでTikTok Studioにログインしてください。")
        print("（Googleアカウント等でのログインも可能です）")
        print()
        print("コンテンツ一覧が表示されたら、ここでEnterを押してください。")
        print("=" * 60)
        input()

        # Verify login succeeded
        if "login" in page.url.lower():
            print("WARNING: まだログインページです。再度ログインしてからEnterを押してください。")
            input()

        print(f"URL: {page.url}")
        print(f"Profile saved to: {PROFILE_DIR}")
        print("次回以降、スクレイパーはこのプロファイルを自動で使用します。")
        context.close()


if __name__ == "__main__":
    main()
