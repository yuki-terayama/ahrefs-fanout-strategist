"""Ahrefs Brand Radar API v3 ラッパー（POST + 構造化リクエスト）。

公開ドキュメント: https://docs.ahrefs.com/ja/api/reference/brand-radar

UI から取得した正規のリクエスト形式（cURL）に準拠:
- HTTPメソッド: POST
- brands/competitors は {"names": [...], "url_groups": [{"target": ..., "scope": ...}]} の構造化
- country / data_source は配列

主要エンドポイント:
- brand-radar/ai-responses: AIの応答 + ファンアウトクエリ(search_queries) + 引用元URL

ファンアウトクエリ仕様:
- data_source が chatgpt または perplexity のときのみ search_queries が非空
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import requests

from . import common

AHREFS_API_BASE = "https://api.ahrefs.com/v3"
DEFAULT_TIMEOUT = 120

DEFAULT_SELECT = [
    "question",
    "response",
    "volume",
    "country",
    "links",
    "search_queries",
    "tags",
    "data_source",
    "last_updated",
]


def _headers() -> dict:
    api_key = common.require_env("AHREFS_API_KEY")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def build_brand_entry(name: str, target_domain: str, scope: str = "subdomains") -> dict:
    """brands/competitors の1エントリを生成するヘルパー。

    Args:
        name: ブランド名（例: "Ahrefs"）
        target_domain: 対象ドメイン（例: "ahrefs.com"）
        scope: "subdomains" | "exact" | "prefix" 等

    Returns:
        {"names": [name], "url_groups": [{"target": target_domain, "scope": scope}]}
    """
    return {
        "names": [name],
        "url_groups": [{"target": target_domain, "scope": scope}],
    }


def fetch_ai_responses(
    brands: list[dict],
    competitors: list[dict],
    country: Optional[list[str]] = None,
    data_source: Optional[list[str]] = None,
    date_str: Optional[str] = None,
    select: Optional[list[str]] = None,
    limit: int = 1000,
    order_by: str = "relevance",
) -> list[dict]:
    """Brand Radar の AI Responses を1日分取得。

    Args:
        brands: [{"names": ["Ahrefs"], "url_groups": [{"target": "ahrefs.com", "scope": "subdomains"}]}, ...]
        competitors: 同様の構造のリスト
        country: ["jp"] 等の ISO-3166-1 alpha-2 リスト
        data_source: ["chatgpt", "perplexity"] 等
        date_str: 取得対象日（YYYY-MM-DD）。未指定だとAPIが直近1日を返す
        select: 取得するフィールドのリスト
        limit: 最大件数（UI 上の149件全部を取りたいので 1000 推奨）
        order_by: "relevance" | "volume"

    Returns:
        ai_responses 配列。各要素のキー:
        question, response, search_queries, links, volume,
        data_source, tags, country, last_updated
    """
    if country is None:
        country = ["jp"]
    if data_source is None:
        data_source = ["chatgpt", "perplexity"]
    if select is None:
        select = DEFAULT_SELECT

    body: dict = {
        "brands": brands,
        "competitors": competitors,
        "data_source": data_source,
        "country": country,
        "order_by": order_by,
        "limit": limit,
        "select": select,
    }
    if date_str:
        body["date"] = date_str

    resp = requests.post(
        f"{AHREFS_API_BASE}/brand-radar/ai-responses",
        headers=_headers(),
        json=body,
        timeout=DEFAULT_TIMEOUT,
    )
    if not resp.ok:
        try:
            err = resp.json()
        except Exception:
            err = {"text": resp.text[:500]}
        raise RuntimeError(
            f"Brand Radar API error: HTTP {resp.status_code} {err}"
        )
    data = resp.json()
    return data.get("ai_responses", [])


def fetch_ai_responses_for_period(
    brands: list[dict],
    competitors: list[dict],
    country: Optional[list[str]] = None,
    data_source: Optional[list[str]] = None,
    days: int = 7,
    select: Optional[list[str]] = None,
    limit: int = 1000,
    order_by: str = "relevance",
    end_date: Optional[date] = None,
    on_day_done=None,
) -> list[dict]:
    """直近 days 日分の AI 応答を取得して結合（重複は残す。集計時にプロンプト単位で集約する想定）。

    Args:
        end_date: 起点となる日（含む）。未指定は今日
        on_day_done: 各日取得後に呼ばれるコールバック（進捗表示用）

    Returns:
        days 日分の応答を flatten した配列
    """
    end_date = end_date or date.today()
    all_responses: list[dict] = []
    for i in range(days):
        d = end_date - timedelta(days=i)
        ds = d.isoformat()
        responses = fetch_ai_responses(
            brands=brands,
            competitors=competitors,
            country=country,
            data_source=data_source,
            date_str=ds,
            select=select,
            limit=limit,
            order_by=order_by,
        )
        all_responses.extend(responses)
        if on_day_done:
            on_day_done(ds, len(responses))
    return all_responses
