"""Brand Radar API の件数違いの原因を調査するスクリプト。

UI で 149件見えるはずなのに API では 23件しか返らない原因を仮説検証する。

仮説:
- A: date 未指定だと API が直近1日のみ返している
- B: brand/competitors パラメータでAPI側が絞り込みしている
- C: response 列指定（10ユニット消費）が limit を引いている
- D: その他
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.lib import brand_radar, common

BRAND = "Ahrefs"
COMPETITORS = "Semrush,ubersuggest,キーワードマップ,TACT SEO,ミエルカSEO"

LIGHT_SELECT = "question,search_queries,data_source,volume,tags,last_updated"  # response 含まない（軽量・コスト節約）
FULL_SELECT = "question,response,search_queries,links,volume,data_source,tags,last_updated"


def _summarize(label: str, responses: list[dict]) -> None:
    print(f"\n--- {label} ---")
    print(f"件数: {len(responses)}")
    if not responses:
        return
    # ユニーク question 数
    unique_q = {r.get("question", "") for r in responses}
    print(f"ユニーク question: {len(unique_q)}")
    # last_updated の分布
    dates = sorted({(r.get("last_updated") or "")[:10] for r in responses if r.get("last_updated")})
    print(f"last_updated 日付一覧: {dates}")
    # data_source の分布
    sources = {}
    for r in responses:
        s = r.get("data_source", "?")
        sources[s] = sources.get(s, 0) + 1
    print(f"data_source 内訳: {sources}")


def main() -> int:
    print("=== Brand Radar API 件数違い原因調査 ===\n")

    # パターン1: 今回の e2e と同じ条件
    print("# パターン1: brand+competitors, date 未指定, response 含む (e2e と同じ)")
    r1 = brand_radar.fetch_ai_responses(
        brand=BRAND, competitors=COMPETITORS, country="jp",
        data_source="chatgpt,perplexity",
        select=FULL_SELECT, limit=1000,
    )
    _summarize("p1", r1)

    # パターン2: response 列を抜く（軽量）
    print("\n# パターン2: brand+competitors, date 未指定, response 含まない")
    r2 = brand_radar.fetch_ai_responses(
        brand=BRAND, competitors=COMPETITORS, country="jp",
        data_source="chatgpt,perplexity",
        select=LIGHT_SELECT, limit=1000,
    )
    _summarize("p2", r2)

    # パターン3: brand だけ
    print("\n# パターン3: brand のみ, date 未指定")
    r3 = brand_radar.fetch_ai_responses(
        brand=BRAND, competitors="", country="jp",
        data_source="chatgpt,perplexity",
        select=LIGHT_SELECT, limit=1000,
    )
    _summarize("p3", r3)

    # パターン4: competitors だけ
    print("\n# パターン4: competitors のみ, date 未指定")
    r4 = brand_radar.fetch_ai_responses(
        brand="", competitors=COMPETITORS, country="jp",
        data_source="chatgpt,perplexity",
        select=LIGHT_SELECT, limit=1000,
    )
    _summarize("p4", r4)

    # パターン5: date を直近7日分ループ
    print("\n# パターン5: brand+competitors を 7日分の date 個別指定 → 結合")
    today = date.today()
    all_p5: list[dict] = []
    per_day_counts: dict[str, int] = {}
    for i in range(7):
        d = today - timedelta(days=i)
        ds = d.isoformat()
        try:
            r = brand_radar.fetch_ai_responses(
                brand=BRAND, competitors=COMPETITORS, country="jp",
                data_source="chatgpt,perplexity",
                select=LIGHT_SELECT, limit=1000, date=ds,
            )
            per_day_counts[ds] = len(r)
            all_p5.extend(r)
        except Exception as e:
            per_day_counts[ds] = f"ERROR: {e}"
    print(f"日付ごと件数: {json.dumps(per_day_counts, ensure_ascii=False, indent=2)}")
    print(f"合計（重複含む）: {len(all_p5)}")
    unique_q = {r.get("question", "") for r in all_p5}
    print(f"ユニーク question: {len(unique_q)}")

    # 保存
    out_dir = common.ensure_output_dir("test")
    summary = {
        "p1_brand_competitors_default_date_full": len(r1),
        "p2_brand_competitors_default_date_light": len(r2),
        "p3_brand_only_default_date": len(r3),
        "p4_competitors_only_default_date": len(r4),
        "p5_7days_summed": len(all_p5),
        "p5_unique_question": len(unique_q),
        "p5_per_day": per_day_counts,
    }
    (out_dir / "debug_brand_radar_count.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n保存: {out_dir / 'debug_brand_radar_count.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
