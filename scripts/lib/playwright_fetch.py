"""Playwright (patchright) で任意の Web ページの本文を取得する。

WebFetch が動的レンダリングサイトで取得失敗（"Content truncated due to length" 等）した場合の
フォールバックとして使用する。

主な用途:
- Phase 0: 自社サイトのビジネスモデル調査
- Phase 9: 引用元ページ・自社既存ページの本文取得（必要に応じて）
"""
from __future__ import annotations

import time

from patchright.sync_api import sync_playwright

from . import common

USER_DATA_DIR = common.PROJECT_ROOT / ".chrome_user_data"


def fetch_page_text(url: str, headless: bool = False, timeout_ms: int = 30_000,
                    wait_after_load_sec: int = 3) -> str:
    """指定 URL のページを開いて本文テキスト（document.body.innerText）を返す。

    動的レンダリング後の本文を取得するため、load 後に少し待機する。
    """
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(USER_DATA_DIR),
            channel="chrome",
            headless=headless,
            no_viewport=True,
            locale="ja-JP",
            timezone_id="Asia/Tokyo",
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            time.sleep(wait_after_load_sec)
            text = page.evaluate("() => document.body ? document.body.innerText : ''") or ""
            return text
        finally:
            context.close()


def fetch_pages_text(urls: list[str], headless: bool = False, timeout_ms: int = 30_000,
                     wait_after_load_sec: int = 3) -> dict[str, str]:
    """複数 URL を1セッション内で順次取得して dict で返す。

    1セッション（同一 context）で順次取得することで、ブラウザ起動オーバーヘッドを削減。
    """
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    results: dict[str, str] = {}
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(USER_DATA_DIR),
            channel="chrome",
            headless=headless,
            no_viewport=True,
            locale="ja-JP",
            timezone_id="Asia/Tokyo",
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            for url in urls:
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                    time.sleep(wait_after_load_sec)
                    text = page.evaluate("() => document.body ? document.body.innerText : ''") or ""
                    results[url] = text
                except Exception as e:
                    results[url] = f"ERROR: {type(e).__name__}: {e}"
        finally:
            context.close()
    return results
