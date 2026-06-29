"""ahrefs-fanout-strategist メインエントリーポイント。

データソースを `api`（Brand Radar API直接）または `csv`（UIエクスポートCSV読込）で切り替え可能。

使い方:
  # API モード（Ahrefs API ユニット消費）
  python scripts/main.py --source api \\
      --brand-name Ahrefs --brand-url ahrefs.com \\
      --competitor "Semrush=semrush.com" \\
      --competitor "ubersuggest=neilpatel.com" \\
      --days 7

  # CSV モード（input/ 配下の Brand Radar UI CSV を読込）
  python scripts/main.py --source csv \\
      --brand-name Ahrefs \\
      --input-dir input

  # site:検索の実行件数（デフォルト 0 = 全件）
  python scripts/main.py --source csv --site-search-limit 10
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.lib import aggregation, brand_radar, common, csv_loader, web_search_playwright, xlsx_export

# デフォルト：プロンプトに含まれていたら関連性が低いとみなす競合語フラグメント
DEFAULT_COMPETITOR_PHRASES = [
    "semrush", "ubersuggest", "neil patel", "neilpatel",
    "キーワードマップ", "tact seo", "tact-seo", "ミエルカ", "ミエルカseo",
]


def _parse_competitor_arg(arg: str) -> tuple[str, str]:
    """`Name=domain.com` 形式をパース"""
    if "=" not in arg:
        raise ValueError(f"競合指定は 'Name=domain.com' 形式: '{arg}'")
    name, domain = arg.split("=", 1)
    return name.strip(), domain.strip()


def _load_competitors_file(path: Path) -> list[tuple[str, str]]:
    """競合JSONファイルを読み込む。

    形式: [{"name": "Semrush", "domain": "semrush.com"}, ...]
    Phase 0 で Claude が生成・ユーザーが確定したものを想定。
    """
    import json
    data = json.loads(path.read_text(encoding="utf-8"))
    return [(c["name"], c["domain"]) for c in data]


def fetch_responses_via_api(
    brand_name: str,
    brand_url: str,
    competitors: list[tuple[str, str]],
    days: int,
) -> list[dict]:
    brands = [brand_radar.build_brand_entry(brand_name, brand_url, "subdomains")]
    comp_entries = [
        brand_radar.build_brand_entry(name, url, "subdomains")
        for name, url in competitors
    ]

    def on_day(ds: str, count: int) -> None:
        print(f"  {ds}: {count} 件")

    print(f"=== API モード: Brand Radar から {days}日分取得 ===")
    return brand_radar.fetch_ai_responses_for_period(
        brands=brands,
        competitors=comp_entries,
        country=["jp"],
        data_source=["chatgpt", "perplexity"],
        days=days,
        limit=1000,
        on_day_done=on_day,
    )


def fetch_responses_via_csv(input_dir: Path) -> list[dict]:
    print(f"=== CSV モード: {input_dir} から読込 ===")
    csv_files = sorted(input_dir.glob("*.csv"))
    print(f"CSV ファイル数: {len(csv_files)}")
    for p in csv_files:
        print(f"  - {p.name}")
    return csv_loader.load_brand_radar_csvs(input_dir)


def run(
    source: str,
    brand_name: str,
    brand_url: str,
    competitors: list[tuple[str, str]],
    days: int,
    input_dir: Path,
    site_search_limit: int,
    competitor_phrases: list[str] | None = None,
    include_only_file: Path | None = None,
) -> int:
    competitor_phrases = competitor_phrases or DEFAULT_COMPETITOR_PHRASES

    include_only: set[str] | None = None
    if include_only_file:
        text = include_only_file.read_text(encoding="utf-8")
        include_only = {line.strip() for line in text.splitlines() if line.strip()}
        print(f"=== 関連プロンプト限定モード: {len(include_only)} 件のみ処理 ===")

    # Phase 2: データ取得
    if source == "api":
        responses = fetch_responses_via_api(brand_name, brand_url, competitors, days)
    else:
        responses = fetch_responses_via_csv(input_dir)

    print(f"\n総取得件数（重複含む）: {len(responses)}")
    unique_q = {r.get("question", "") for r in responses if r.get("question")}
    print(f"ユニーク question 数: {len(unique_q)}")

    # Phase 3: 競合名スクリーニング
    print("\n=== Phase 3: 競合名スクリーニング ===")
    screened, excluded = [], 0
    for r in responses:
        q = (r.get("question") or "").lower()
        if any(c in q for c in competitor_phrases):
            excluded += 1
            continue
        screened.append(r)
    print(f"競合名で除外: {excluded} 件")
    print(f"スクリーニング後: {len(screened)} 件")

    # Phase 3 追加: ビジネスモデル関連性フィルタ（include_only_file 指定時）
    if include_only is not None:
        before = len(screened)
        screened = [r for r in screened if r.get("question") in include_only]
        print(f"関連プロンプト限定後: {len(screened)} 件 (関連性で除外 {before - len(screened)} 件)")

    # Phase 5: 集計（プラットフォーム別）
    print("\n=== Phase 5: (プロンプト × プラットフォーム) 単位で集計 ===")
    mention = aggregation.mention_rate_by_query(screened, brand_name)
    print(f"ユニーク (question, platform) 数: {len(mention)}")
    no_mention_keys = [k for k, v in mention.items() if v["rate"] == 0]
    with_mention_keys = [k for k, v in mention.items() if v["rate"] > 0]
    print(f"  自社言及あり: {len(with_mention_keys)} 件")
    print(f"  自社言及なし: {len(no_mention_keys)} 件")

    # Phase 6: site:検索（プラットフォーム別）
    # ファンアウトクエリ優先、空ならプロンプト本文（判断1=B, 判断2=E）
    from collections import defaultdict
    by_key_responses: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in screened:
        key = (r.get("question") or "", r.get("data_source") or "")
        by_key_responses[key].append(r)

    site_search_results: dict[tuple[str, str], list[dict]] = {}
    if site_search_limit == 0:
        targets = no_mention_keys
        print(f"\n=== Phase 6: site:検索（言及なし (question×platform) 全 {len(targets)} 件、Playwright）===")
    else:
        targets = no_mention_keys[:site_search_limit]
        print(f"\n=== Phase 6: site:検索（言及なし (question×platform) 上位 {len(targets)} 件、Playwright、テスト用）===")
    for i, key in enumerate(targets, start=1):
        question, platform = key
        resp_list = by_key_responses.get(key, [])
        # ファンアウトクエリ優先、なければプロンプト本文（判断1=B）
        fanout = aggregation.representative_fanout_query(resp_list)
        search_query = fanout if fanout else question
        used_label = "fanout" if fanout else "prompt"
        q_disp = search_query[:60] + ("..." if len(search_query) > 60 else "")
        print(f"  [{i}/{len(targets)}] ({platform}, {used_label}) {q_disp}")
        try:
            results = web_search_playwright.site_search_top3(brand_url, search_query)
            site_search_results[key] = results
            print(f"    取得: {len(results)} 件")
        except Exception as e:
            print(f"    ERROR: {e}")
            site_search_results[key] = []

    # Phase 7: XLSX出力
    print("\n=== Phase 7: マッピング XLSX 出力 ===")
    rows = aggregation.build_mapping_rows(
        screened,
        brand_name,
        intents={},
        site_search_results=site_search_results,
    )
    xlsx_path = xlsx_export.export_mapping(rows, brand_url.replace(".", "_"))
    print(f"行数:   {len(rows)}")
    print(f"出力先: {xlsx_path}")

    summary = {
        "source": source,
        "total_rows": len(responses),
        "unique_questions": len(unique_q),
        "screened": len(screened),
        "excluded_by_competitor_name": excluded,
        "with_mention_pairs": len(with_mention_keys),
        "no_mention_pairs": len(no_mention_keys),
        "site_search_target_prompts": len(targets),
        "xlsx": str(xlsx_path),
    }
    summary_path = common.ensure_output_dir() / "run_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"サマリ: {summary_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="ahrefs-fanout-strategist")
    parser.add_argument("--source", choices=["api", "csv"], default="api",
                        help="データ取得元: api=Brand Radar API直接 / csv=UIエクスポートCSV")
    parser.add_argument("--brand-name", required=True, help="自社ブランド名 (例: Ahrefs)")
    parser.add_argument("--brand-url", required=True, help="自社ドメイン (例: ahrefs.com)")
    parser.add_argument("--competitor", action="append", default=[],
                        help="競合 'Name=domain.com' 形式。複数回指定可")
    parser.add_argument("--competitors-file", type=str, default=None,
                        help="競合リストJSONファイル ([{name, domain}, ...])。Phase 0 で生成したものを指定")
    parser.add_argument("--days", type=int, default=7, help="API モード時の取得日数 (デフォルト 7)")
    parser.add_argument("--input-dir", default="input", help="CSV モード時の入力ディレクトリ")
    parser.add_argument("--site-search-limit", type=int, default=0,
                        help="site:検索の実行件数。0=全件、N=言及なし上位N件のみ（コスト節約）")
    parser.add_argument("--include-only-file", type=str, default=None,
                        help="関連プロンプトリスト（1行1プロンプト）のテキストファイル。指定時はこのリストに含まれるプロンプトのみ処理")
    args = parser.parse_args()

    competitors = [_parse_competitor_arg(c) for c in args.competitor]
    if args.competitors_file:
        competitors.extend(_load_competitors_file(Path(args.competitors_file)))
    return run(
        source=args.source,
        brand_name=args.brand_name,
        brand_url=args.brand_url,
        competitors=competitors,
        days=args.days,
        input_dir=Path(args.input_dir),
        site_search_limit=args.site_search_limit,
        include_only_file=Path(args.include_only_file) if args.include_only_file else None,
    )


if __name__ == "__main__":
    sys.exit(main())
