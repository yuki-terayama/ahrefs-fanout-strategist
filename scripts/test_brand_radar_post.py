"""POST 版 Brand Radar API の動作確認。

1日分（2026-06-25）で 149 件取れるか確認する。
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.lib import brand_radar

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


def main() -> int:
    print("=== POST 版 Brand Radar API 動作確認 ===")
    print()
    print("# 1日分テスト (date=2026-06-25, limit=1000)")
    try:
        responses = brand_radar.fetch_ai_responses(
            brands=BRANDS,
            competitors=COMPETITORS,
            country=["jp"],
            data_source=["chatgpt", "perplexity"],
            date_str="2026-06-25",
            limit=1000,
        )
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        return 1

    print(f"取得件数: {len(responses)}")
    if responses:
        unique_q = {r.get("question", "") for r in responses}
        sources = {}
        for r in responses:
            s = r.get("data_source", "?")
            sources[s] = sources.get(s, 0) + 1
        print(f"ユニーク question: {len(unique_q)}")
        print(f"data_source 内訳: {sources}")

        # サンプル
        sample = responses[0]
        print()
        print("--- サンプル1件目 ---")
        print(f"data_source: {sample.get('data_source')}")
        print(f"question: {sample.get('question', '')[:80]}")
        print(f"search_queries: {sample.get('search_queries')}")
        print(f"links数: {len(sample.get('links', []))}")
        print(f"volume: {sample.get('volume')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
