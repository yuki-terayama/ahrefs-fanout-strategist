"""Brand Radar API 接続テスト。

Ahrefs を対象に brand-radar/ai-responses を呼び出して、
ファンアウトクエリ (search_queries) が取れるか確認する。
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.lib import brand_radar, common

BRAND = "Ahrefs"
COMPETITORS = "Semrush,ubersuggest,キーワードマップ,TACT SEO,ミエルカSEO"


def main() -> int:
    print(f"=== Brand Radar API 接続テスト ===")
    print(f"Brand:       {BRAND}")
    print(f"Competitors: {COMPETITORS}")
    print(f"Country:     jp")
    print(f"Data source: chatgpt,perplexity")
    print()

    try:
        responses = brand_radar.fetch_ai_responses(
            brand=BRAND,
            competitors=COMPETITORS,
            country="jp",
            data_source="chatgpt,perplexity",
            limit=10,
        )
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1

    print(f"取得件数: {len(responses)}")
    if not responses:
        print("(0件。brand/competitors の指定や report_id が必要かもしれません)")
        return 0

    sample = responses[0]
    print("\n=== サンプル1件目 ===")
    print(f"data_source: {sample.get('data_source')}")
    q = sample.get("question", "")
    print(f"question: {q[:100]}{'...' if len(q) > 100 else ''}")
    sq = sample.get("search_queries", [])
    print(f"search_queries (ファンアウト): {sq}")
    links = sample.get("links", [])
    print(f"links数: {len(links)}")
    if links:
        print(f"  links[0]: {links[0]}")
    print(f"volume: {sample.get('volume')}")
    print(f"tags: {sample.get('tags')}")

    out_dir = common.ensure_output_dir("test")
    out = out_dir / "brand_radar_ai_responses_sample.json"
    out.write_text(json.dumps(responses, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n全件保存: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
