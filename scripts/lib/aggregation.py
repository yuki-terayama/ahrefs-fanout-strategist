"""集計ロジック（プラットフォーム別）。

集計キー: (question, data_source) のタプル

同じプロンプトでも ChatGPT と Perplexity では：
- ファンアウトクエリが異なる
- 言及されるブランドが異なる
- 引用元ページが異なる

そのため、プラットフォーム別に集計する。
"""
from __future__ import annotations

from collections import Counter, defaultdict

AggKey = tuple[str, str]  # (question, data_source)


def _aggregate_key(response: dict) -> AggKey:
    """集計キー: (プロンプト本文, プラットフォーム)"""
    return (
        response.get("question", "") or "",
        response.get("data_source", "") or "",
    )


def representative_fanout_query(responses_for_key: list[dict]) -> str:
    """同じ集計キー（プロンプト × プラットフォーム）に対する複数応答から
    代表的なファンアウトクエリを1つ選ぶ。

    選び方: 出現頻度が最も多い search_queries の末尾要素。
    """
    counter: Counter = Counter()
    for r in responses_for_key:
        sq = r.get("search_queries") or []
        if sq:
            counter[sq[-1]] += 1
    if not counter:
        return ""
    return counter.most_common(1)[0][0]


def mention_rate_by_query(
    responses: list[dict],
    brand_keyword: str,
) -> dict[AggKey, dict]:
    """(プロンプト × プラットフォーム) ごとの言及率を計算。

    判定優先順位:
    1. mentions 列が存在する場合（CSV由来）: brand_keyword が mentions リストに含まれるか
    2. それ以外（API由来で response 本文がある場合）: response 本文に含まれるか

    Returns:
        {(question, data_source): {"total": int, "mentioned": int, "rate": float}}
    """
    counters: dict[AggKey, dict] = defaultdict(lambda: {"total": 0, "mentioned": 0})
    bk_lower = brand_keyword.lower()
    for r in responses:
        key = _aggregate_key(r)
        if not key[0]:
            continue
        counters[key]["total"] += 1
        mentions = r.get("mentions")
        if mentions is not None:
            if any((m or "").lower() == bk_lower for m in mentions):
                counters[key]["mentioned"] += 1
        else:
            resp_text = (r.get("response") or "").lower()
            if bk_lower in resp_text:
                counters[key]["mentioned"] += 1
    return {
        k: {
            "total": v["total"],
            "mentioned": v["mentioned"],
            "rate": (v["mentioned"] / v["total"]) if v["total"] > 0 else 0.0,
        }
        for k, v in counters.items()
    }


def cited_pages_by_query(
    responses: list[dict],
    top_n: int | None = None,
) -> dict[AggKey, list[dict]]:
    """(プロンプト × プラットフォーム) ごとの引用ページを集計（多い順）。

    Returns:
        {(question, data_source): [{"url": str, "title": str, "count": int}, ...多い順]}
    """
    counters: dict[AggKey, Counter] = defaultdict(Counter)
    title_map: dict[AggKey, dict[str, str]] = defaultdict(dict)
    for r in responses:
        key = _aggregate_key(r)
        if not key[0]:
            continue
        for link in r.get("links") or []:
            url = link.get("url") if isinstance(link, dict) else None
            if not url:
                continue
            counters[key][url] += 1
            if isinstance(link, dict):
                title = link.get("title") or ""
                if title and not title_map[key].get(url):
                    title_map[key][url] = title
    return {
        k: [
            {"url": url, "title": title_map[k].get(url, ""), "count": c}
            for url, c in cnt.most_common(top_n)
        ]
        for k, cnt in counters.items()
    }


# 後方互換エイリアス
top_cited_pages_by_query = cited_pages_by_query


def build_mapping_rows(
    responses: list[dict],
    brand_keyword: str,
    intents: dict[str, str] | None = None,
    site_search_results: dict[AggKey, list[dict]] | None = None,
) -> list[dict]:
    """マッピング表に書き出す行のリストを組み立てる（プラットフォーム別）。

    Args:
        responses: brand_radar / csv_loader の返り値
        brand_keyword: 自社ブランドの検出キーワード
        intents: {question: 検索意図} の辞書（プロンプト単位）
        site_search_results: {(question, platform): site:検索結果リスト}

    Returns:
        プラットフォーム別の行のリスト。同じプロンプトでも ChatGPT 行と Perplexity 行が
        別の行として出力される。言及率昇順、同率なら総応答数少ない順、その後プロンプト名順。
    """
    intents = intents or {}
    site_search_results = site_search_results or {}

    mention = mention_rate_by_query(responses, brand_keyword)
    cited = cited_pages_by_query(responses, top_n=None)

    by_key: dict[AggKey, list[dict]] = defaultdict(list)
    for r in responses:
        key = _aggregate_key(r)
        if not key[0]:
            continue
        by_key[key].append(r)

    rows = []
    for key, resp_list in by_key.items():
        question, platform = key
        m = mention.get(key, {"rate": 0.0, "mentioned": 0, "total": 0})
        fanout = representative_fanout_query(resp_list)
        # 同一プロンプトに対するボリュームは基本同じだが、安全のため最大値を採用
        volume = max((r.get("volume", 0) or 0) for r in resp_list)
        rows.append({
            "platform": platform,
            "prompt": question,
            "volume": volume,
            "fanout_query": fanout,
            "intent": intents.get(question, ""),
            "mention_count": m.get("mentioned", 0),
            "total_count": m.get("total", 0),
            "mention_rate": m.get("rate", 0.0),
            "cited_pages": cited.get(key, []),
            "site_search_results": site_search_results.get(key, []),
        })
    # 言及率昇順 → 検索ボリューム降順 → 総応答数少ない順 → プロンプト名 → プラットフォーム
    rows.sort(key=lambda r: (
        r["mention_rate"],
        -r["volume"],
        r["total_count"],
        r["prompt"],
        r["platform"],
    ))
    return rows
