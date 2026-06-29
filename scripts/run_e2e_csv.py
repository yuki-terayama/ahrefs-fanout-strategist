"""ahrefs-fanout-strategist 一気通貫テスト v3（CSV読み込みベース）。

7日分のCSV（input/ 配下）から読み込み → Phase 3〜7 を実行 → マッピングXLSX出力。

実行内容:
- Phase 2 相当: input/*.csv を全部読み込み
- Phase 3: 競合名スクリーニング
- Phase 5: question 単位で言及率（Mentions列ベース）・引用元トップ10集計
- Phase 6: 言及なしクエリで site:検索（Gemini Grounding）※テスト用に上位N件のみ
- Phase 7: マッピング XLSX 出力
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.lib import aggregation, common, csv_loader, web_search, xlsx_export

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = PROJECT_ROOT / "input"
DOMAIN = "ahrefs.com"
BRAND_KEYWORD = "Ahrefs"
COMPETITOR_PHRASES = [
    "semrush", "ubersuggest", "neil patel", "neilpatel",
    "キーワードマップ", "tact seo", "tact-seo", "ミエルカ", "ミエルカseo",
]

# Phase 6: コスト節約のためテスト用に上位N件のみ site:検索（本番では全件）
SITE_SEARCH_LIMIT_FOR_TEST = 10


def main() -> int:
    print(f"=== Phase 2 相当: CSV読み込み from {INPUT_DIR} ===")
    csv_files = sorted(INPUT_DIR.glob("*.csv"))
    print(f"CSVファイル数: {len(csv_files)}")
    for p in csv_files:
        print(f"  - {p.name}")

    responses = csv_loader.load_brand_radar_csvs(INPUT_DIR)
    print(f"\n総取得件数（重複含む）: {len(responses)}")

    # ユニークquestion数
    unique_q = {r.get("question", "") for r in responses if r.get("question")}
    print(f"ユニーク question 数: {len(unique_q)}")

    print()
    print("=== Phase 3: 競合名スクリーニング ===")
    screened = []
    excluded = 0
    for r in responses:
        q = (r.get("question") or "").lower()
        if any(c in q for c in COMPETITOR_PHRASES):
            excluded += 1
            continue
        screened.append(r)
    print(f"競合名で除外: {excluded} 件")
    print(f"スクリーニング後: {len(screened)} 件")

    print()
    print("=== Phase 5: question 単位で集計 ===")
    mention = aggregation.mention_rate_by_query(screened, BRAND_KEYWORD)
    print(f"ユニーク question 数: {len(mention)}")
    no_mention = [k for k, v in mention.items() if v["rate"] == 0]
    with_mention = [k for k, v in mention.items() if v["rate"] > 0]
    print(f"  自社言及あり: {len(with_mention)} 件")
    print(f"  自社言及なし: {len(no_mention)} 件")

    print()
    print(f"=== Phase 6: site:検索（言及なし上位 {SITE_SEARCH_LIMIT_FOR_TEST} 件、テスト用）===")
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
    print("=== Phase 7: マッピング XLSX 出力 ===")
    rows = aggregation.build_mapping_rows(
        screened,
        BRAND_KEYWORD,
        intents={},
        site_search_results=site_search_results,
    )
    xlsx_path = xlsx_export.export_mapping(rows, DOMAIN.replace(".", "_"))
    print(f"行数:   {len(rows)}")
    print(f"出力先: {xlsx_path}")

    # サマリ JSON も出力（記事執筆の参考データ）
    summary = {
        "csv_files": [p.name for p in csv_files],
        "total_rows": len(responses),
        "unique_questions": len(unique_q),
        "screened": len(screened),
        "excluded_by_competitor_name": excluded,
        "with_mention": len(with_mention),
        "no_mention": len(no_mention),
        "site_search_targets": len(targets),
        "xlsx": str(xlsx_path),
    }
    summary_path = common.ensure_output_dir() / "e2e_csv_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"サマリ: {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
