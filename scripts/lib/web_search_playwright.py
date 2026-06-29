"""Playwright (patchright) を使った Google site:検索。

Gemini Grounding の精度検証 / バックアップ用。
patchright は Playwright の bot 検知回避強化版（CDP リーク・automation フラグ対策内蔵）。

永続Cookie で初回 CAPTCHA を一度通せば以降は自動動作する想定。
"""
from __future__ import annotations

import time
import urllib.parse
from pathlib import Path

from patchright.sync_api import sync_playwright

from . import common

USER_DATA_DIR = common.PROJECT_ROOT / ".chrome_user_data"


def site_search(domain: str, query: str, num: int = 3, headless: bool = False,
                timeout_ms: int = 30_000) -> list[dict]:
    """Google で検索し、上位 num 件を返す。

    domain が指定されていれば `site:domain query`、空なら通常の Google 検索（汎用調査用）。
    返り値: [{"url": "...", "title": "..."}, ...]
    """
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    if domain:
        full_query = f"site:{domain} {query}"
    else:
        full_query = query
    encoded = urllib.parse.quote(full_query)
    url = f"https://www.google.com/search?q={encoded}&hl=ja&gl=jp&num=20"

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
            time.sleep(2)

            # CAPTCHA 検知（body に "通常と異なる" 等が含まれていれば手動対応待ち）
            body_text = page.evaluate("() => document.body ? document.body.innerText : ''") or ""
            if any(k in body_text for k in ["通常と異なる", "unusual traffic", "私はロボット", "I'm not a robot"]):
                if headless:
                    raise RuntimeError("CAPTCHA detected (headless mode). Run with headless=False to solve manually.")
                print("⚠ CAPTCHA を検出しました。ブラウザでチェックを通してください（最大120秒待機）", flush=True)
                # 検索結果が見えるまで待つ（=ユーザーがCAPTCHAを通すまで）
                page.wait_for_function(
                    "() => !!document.querySelector('div#search h3, div[role=\"main\"] h3')",
                    timeout=120_000,
                )
                time.sleep(2)

            # 検索結果が出るまで待つ
            try:
                page.wait_for_selector("h3", timeout=10_000)
            except Exception:
                return []

            # 結果抽出
            results = page.evaluate(
                """
                (n) => {
                    const out = [];
                    const seen = new Set();
                    // h3 を含む結果ブロックを順に走査
                    const heads = document.querySelectorAll('h3');
                    for (const h of heads) {
                        // h3 の祖先 a タグ
                        let a = h.closest('a');
                        if (!a) {
                            // 一つ上の親に a がいる場合もある
                            const parent = h.parentElement;
                            if (parent) a = parent.querySelector('a');
                        }
                        if (!a) continue;
                        const url = a.href || '';
                        if (!url) continue;
                        if (url.startsWith('https://www.google.') ||
                            url.startsWith('https://accounts.google.') ||
                            url.startsWith('https://support.google.') ||
                            url.includes('/search?')) continue;
                        if (seen.has(url)) continue;
                        seen.add(url);
                        out.push({url: url, title: (h.innerText || '').trim()});
                        if (out.length >= n) break;
                    }
                    return out;
                }
                """,
                num,
            )
            return results or []
        finally:
            context.close()


def site_search_top3(domain: str, query: str, headless: bool = False) -> list[dict]:
    return site_search(domain, query, num=3, headless=headless)


def google_search(query: str, num: int = 10, headless: bool = False) -> list[dict]:
    """site:制限なしの通常Google検索。汎用調査（競合特定など）用。"""
    return site_search("", query, num=num, headless=headless)
