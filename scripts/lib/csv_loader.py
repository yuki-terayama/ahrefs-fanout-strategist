"""Brand Radar UI からエクスポートされた CSV を読み込むアダプタ。

CSV フォーマット（Brand Radar UI 由来）:
- エンコーディング: UTF-16 LE（BOM付き）
- 区切り: タブ
- カラム: Country, Keyword, Tags, Volume, Response, Model, Mentions, Fanout Queries,
         Cited pages, Found but not cited, Updated

API の ai-responses レスポンス形式に近い dict 構造に正規化する。
"""
from __future__ import annotations

import csv
from pathlib import Path

CSV_ENCODING = "utf-16"
CSV_DELIMITER = "\t"


def _split_lines(value: str | None) -> list[str]:
    if not value:
        return []
    return [v.strip() for v in value.split("\n") if v.strip()]


def _normalize_model(model: str) -> str:
    """`ChatGPT` -> `chatgpt`, `Perplexity` -> `perplexity` など API 形式に合わせる"""
    return (model or "").strip().lower().replace(" ", "_")


def _parse_volume(value: str | None) -> int:
    if not value:
        return 0
    try:
        return int(value.replace(",", ""))
    except (TypeError, ValueError):
        return 0


def load_brand_radar_csv(csv_path: Path) -> list[dict]:
    """Brand Radar UI からエクスポートされた1ファイルの CSV を読み込み、dict のリストに変換。

    返り値の各要素のキー（API の ai-responses 形式に近い）:
    - country: ISO 3166-1 alpha-2
    - question: プロンプト本文（Keyword 列）
    - tags: タグのリスト
    - volume: 月間検索ボリューム
    - response: AI 応答本文
    - data_source: chatgpt / perplexity 等
    - mentions: 言及されたブランド名のリスト（既に Brand Radar が集計済み）
    - search_queries: ファンアウトクエリのリスト
    - links: 引用元 [{"url": "...", "title": ""}, ...]
    - found_not_cited: 検索発見したが未引用 [{"url": "..."}, ...]
    - last_updated: 更新日（YYYY-MM-DD）
    """
    responses: list[dict] = []
    with open(csv_path, "r", encoding=CSV_ENCODING) as f:
        reader = csv.DictReader(f, delimiter=CSV_DELIMITER)
        for row in reader:
            mentions = _split_lines(row.get("Mentions"))
            fanout = _split_lines(row.get("Fanout Queries"))
            cited_urls = _split_lines(row.get("Cited pages"))
            found_not_cited = _split_lines(row.get("Found but not cited"))
            tags = [
                t.strip()
                for t in (row.get("Tags") or "").replace("\n", ",").split(",")
                if t.strip()
            ]
            responses.append({
                "country": (row.get("Country") or "").strip(),
                "question": (row.get("Keyword") or "").strip(),
                "tags": tags,
                "volume": _parse_volume(row.get("Volume")),
                "response": row.get("Response") or "",
                "data_source": _normalize_model(row.get("Model") or ""),
                "mentions": mentions,
                "search_queries": fanout,
                "links": [{"url": u, "title": ""} for u in cited_urls],
                "found_not_cited": [{"url": u} for u in found_not_cited],
                "last_updated": (row.get("Updated") or "").strip(),
            })
    return responses


def load_brand_radar_csvs(input_dir: Path, dedupe: bool = True) -> list[dict]:
    """input_dir 配下の全 CSV を読み込んで結合（7日分など複数日対応）。

    Args:
        input_dir: CSV を置いたディレクトリ
        dedupe: (question, data_source, last_updated) で重複除去するか。
                Brand Radar のCSVは応答が更新されない限り同じ応答が翌日以降にも
                含まれるため、複数日のCSVを結合すると同一応答を多重カウントする。
                デフォルトは True（実応答ベースで集計）。

    .gitkeep など .csv 以外は無視。
    """
    all_responses: list[dict] = []
    for csv_path in sorted(input_dir.glob("*.csv")):
        responses = load_brand_radar_csv(csv_path)
        all_responses.extend(responses)

    if dedupe:
        seen: set[tuple[str, str, str]] = set()
        unique: list[dict] = []
        for r in all_responses:
            key = (
                r.get("question", "") or "",
                r.get("data_source", "") or "",
                r.get("last_updated", "") or "",
            )
            if key in seen:
                continue
            seen.add(key)
            unique.append(r)
        return unique

    return all_responses
