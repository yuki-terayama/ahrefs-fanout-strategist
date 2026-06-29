"""ahrefs-fanout-strategist 一気通貫テスト v2（POST + 7日分対応）。

実行内容:
- Phase 2: Brand Radar 7日分取得（POST、構造化リクエスト）
- Phase 3: 競合名スクリーニング（ビジネスモデル関連性スクリーニングは別途Claude判定）
- Phase 5: question 単位で言及率・引用元トップ10集計
- Phase 6: 言及なしクエリの上位N件で site:検索（Gemini）
- Phase 7: マッピング XLSX 出力
"""
import json
import sys
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.lib import aggregation, brand_radar, common, web_search, xlsx_export

DOMAIN = "ahrefs.com"
BRAND_KEYWORD = "Ahrefs"

BRANDS = [
    brand_radar.build_brand_entry("Ahrefs", "ahrefs.com", "subdomains"),
]
COMPETITORS = [
    brand_radar.build_brand_entry("Semrush", "semrush.com", "subdomains"),
    brand_radar.build_brand_entry("ubersuggest", "neilpatel.com", "subdomains"),
    brand_radar.build_brand_entry("キーワードマップ", "keywordmap.jp", "subdomains"),
    brand_radar.build_brand_entry("TACT SEO", "tact-seo.com", "subdomains"),
    brand_radar.build_brand_entry("ミエルカSEO", "mieru-ca.com", "subdomains"),
]
COMPETITOR_PHRASES = [
    "semrush", "ubersuggest", "neil patel", "neilpatel",
    "キーワードマップ", "tact seo", "tact-seo", "ミエルカ", "ミエルカseo",
]

# Phase 6: コスト節約のため、言及なしクエリのうち上位 N 件のみ site:検索（本番は全件）
SITE_SEARCH_LIMIT_FOR_TEST = 10


def main() -> int:
    print(f"=== Phase 2: Brand Radar 7日分取得 ===")

    def on_day(ds: str, count: int) -> None:
        print(f"  {ds}: {count} 件")

    responses = brand_radar.fetch_ai_responses_for_period(
        brands=BRANDS,
        competitors=COMPETITORS,
        country=["jp"],
        data_source=["chatgpt", "perplexity"],
        days=7,
        limit=1000,
        on_day_done=on_day,
    )
    print(f"\n7日分合計（重複含む）: {len(responses)} 件")
    out_dir = common.ensure_output_dir("test")
    (out_dir / "phase2_responses_7days.json").write_text(
        json.dumps(responses, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print()
    print(f"=== Phase 3: 競合名スクリーニング ===")
    screened = []
    excluded = 0
    for r in responses:
        q = (r.get("question") or "").lower()
        if any(c in q for c in COMPETITOR_PHRASES):
            excluded += 1
            continue
        screened.append(r)
    print(f"競合名で除外: {excluded} 件")
    print(f"スクリーニング後（プロンプト関連性は別途 Claude 判定が必要）: {len(screened)} 件")

    print()
    print(f"=== Phase 5: question 単位で集計 ===")
    mention = aggregation.mention_rate_by_query(screened, BRAND_KEYWORD)
    print(f"ユニーク question 数: {len(mention)}")

    no_mention = [k for k, v in mention.items() if v["rate"] == 0]
    with_mention = [k for k, v in mention.items() if v["rate"] > 0]
    print(f"  自社言及あり: {len(with_mention)} 件")
    print(f"  自社言及なし: {len(no_mention)} 件")

    print()
    print(f"=== Phase 6: site:検索 (言及なしクエリ上位 {SITE_SEARCH_LIMIT_FOR_TEST} 件のみテスト) ===")
    site_search_results: dict[str, list[dict]] = {}
    targets = no_mention[:SITE_SEARCH_LIMIT_FOR_TEST]
    for i, q in enumerate(targets, start=1):
        q_disp = q[:60] + ("..." if len(q) > 60 else "")
        print(f"  [{i}/{len(targets)}] {q_disp}")
        try:
            results = web_search.site_search_top3(DOMAIN, q)
            site_search_results[q] = results
            print(f"    取得: {len(results)} 件")
        except Exception as e:
            print(f"    ERROR: {e}")
            site_search_results[q] = []

    print()
    print(f"=== Phase 7: マッピング XLSX 出力 ===")
    rows = aggregation.build_mapping_rows(
        screened,
        BRAND_KEYWORD,
        intents={},  # 検索意図は Claude 対話で別途生成
        site_search_results=site_search_results,
    )
    xlsx_path = xlsx_export.export_mapping(rows, DOMAIN.replace(".", "_"))
    print(f"行数:   {len(rows)}")
    print(f"出力先: {xlsx_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
