"""Phase 4: 検索意図解釈（オンデマンド）の素材収集スクリプト。

Phase 8 で対策クエリが1件選ばれたあと、Phase 9 のステップ1としても呼ばれる。
ここでは「素材を集めて Claude Code に渡す」までを担当する：

1. CSV から指定 (prompt, platform) に該当する全応答を抽出
2. 代表ファンアウトクエリと全応答のファンアウト・mentions・応答冒頭を `target_info.md` に整形
3. 出力先: output/phase4/{slug}/target_info.md

Claude Code は target_info.md を読んで、AI のプロンプト解釈を言語化する。

使い方:
  python scripts/phase4_intent.py \\
      --brand-name "Ahrefs" \\
      --brand-url "ahrefs.com" \\
      --prompt "無料のSEO分析ツールは？" \\
      --platform "perplexity" \\
      --input-dir input
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.lib import aggregation, common, csv_loader
from scripts.main import DEFAULT_COMPETITOR_PHRASES


def to_slug(prompt: str, platform: str, max_len: int = 30) -> str:
    """Windows ファイル名に使える形に変換"""
    safe = re.sub(r'[\\/:*?"<>|\n\r\t]', "", prompt).strip()[:max_len]
    return f"{platform}_{safe}"


def build_target_info_md(
    prompt: str,
    platform: str,
    brand_name: str,
    target_resps: list[dict],
) -> str:
    """対象 (prompt, platform) の応答群から検索意図解釈用の素材 md を生成"""
    bk = brand_name.lower()
    mentioned_count = sum(
        1
        for r in target_resps
        if any((m or "").lower() == bk for m in (r.get("mentions") or []))
    )
    fanout = aggregation.representative_fanout_query(target_resps)

    lines = [
        f"# Phase 4 検索意図解釈 素材: {prompt} ({platform})",
        "",
        "## メタ情報",
        f"- プロンプト: {prompt}",
        f"- プラットフォーム: {platform}",
        f"- 応答数: {len(target_resps)}",
        f"- 自社（{brand_name}）言及応答数: {mentioned_count}",
        f"- 代表ファンアウトクエリ: {fanout or '(なし)'}",
        "",
        "## 全応答の詳細（新しい順）",
        "",
    ]

    sorted_resps = sorted(
        target_resps, key=lambda r: r.get("last_updated", ""), reverse=True
    )
    for i, r in enumerate(sorted_resps, 1):
        sq = r.get("search_queries") or []
        mentions = r.get("mentions") or []
        updated = r.get("last_updated", "")
        resp_text = (r.get("response") or "").strip()
        lines.append(f"### 応答 {i} ({updated})")
        lines.append(f"- mentions: {', '.join(mentions) if mentions else '(なし)'}")
        lines.append(
            f"- ファンアウトクエリ: {', '.join(sq) if sq else '(なし)'}"
        )
        lines.append("- 応答冒頭 (500 字):")
        lines.append("")
        lines.append("```")
        lines.append(resp_text[:500])
        lines.append("```")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Claude Code への指示")
    lines.append("")
    lines.append(
        "**ファンアウトクエリの語のみ** を見て検索意図を解釈する。応答本文は使わない"
        "（応答本文は AI が組み立てた答えであり、ユーザーの需要の証拠ではない）。"
    )
    lines.append("")
    lines.append("### 手順")
    lines.append("1. ファンアウトクエリの語を機械的に分解")
    lines.append("2. 各語を「直訳語」か「幅あり語」に分類")
    lines.append("3. 直訳語 → 1つに確定して変換")
    lines.append("4. 幅あり語 → **絞り込まず、主要候補を列挙したまま残す**")
    lines.append(
        "5. 合成して1文で表現（幅あり語は「○○ / △△ / □□ などのいずれか or 複数」と書く）"
    )
    lines.append("6. 単語変換表（語 / 種別 / 解釈 or 候補）を併記")
    lines.append("")
    lines.append("### NG")
    lines.append(
        "- 解釈幅のある語を1つの候補に決め打ちする（→ 主要候補を列挙したまま残す）"
    )
    lines.append(
        "- ファンアウトクエリに登場しない要素（想定読者層・推奨スタンス・カバレッジ軸・優先順位など）を後付けで追加する"
    )
    lines.append(
        "- 応答本文の見出し構造・列挙順・語彙を解釈の根拠に使う（応答は AI の「答え」であり需要の証拠ではない）"
    )
    lines.append("")
    lines.append("### 例")
    lines.append("ファンアウトクエリ: `無料のSEO分析ツールは？`")
    lines.append("")
    lines.append("| 語 | 種別 | 解釈 / 候補 |")
    lines.append("|---|---|---|")
    lines.append("| 無料 | 直訳 | 予算ゼロで |")
    lines.append("| SEO | 直訳 | 検索エンジン最適化のために |")
    lines.append(
        "| 分析 | 幅あり | 自社サイト診断 / 競合分析 / キーワード分析 / 順位分析 / 被リンク分析 などのいずれか or 複数 |"
    )
    lines.append("| ツール | 直訳 | ツールが欲しい |")
    lines.append("")
    lines.append(
        "解釈: 予算ゼロで使える、SEO の何らか（自社サイト診断・競合分析・キーワード調査・順位調査・被リンク分析 など）ができるツールを探している。"
    )

    return "\n".join(lines)


def run(
    brand_name: str,
    brand_url: str,
    prompt: str,
    platform: str,
    input_dir: Path,
) -> int:
    slug = to_slug(prompt, platform)
    out_dir = common.ensure_output_dir(f"phase4/{slug}")

    print(f"=== Phase 4: 検索意図解釈の素材収集 ===")
    print(f"対象: {platform} / {prompt}")
    print(f"出力先: {out_dir}")

    print(f"\n[1/3] CSV ロード ({input_dir})")
    all_responses = csv_loader.load_brand_radar_csvs(input_dir)
    print(f"  総応答数（重複除去後）: {len(all_responses)}")

    # 競合スクリーニング
    screened = [
        r
        for r in all_responses
        if not any(c in (r.get("question") or "").lower() for c in DEFAULT_COMPETITOR_PHRASES)
    ]
    print(f"  競合名スクリーニング後: {len(screened)}")

    print(f"\n[2/3] 対象 (prompt, platform) の応答抽出")
    target_resps = [
        r
        for r in screened
        if r.get("question") == prompt and r.get("data_source") == platform
    ]
    print(f"  対象応答数: {len(target_resps)}")
    if not target_resps:
        print(f"  ERROR: 対象応答が見つかりません")
        print(f"    --prompt: {prompt!r}")
        print(f"    --platform: {platform!r}")
        # ヒント: 該当 platform でユニーク question を列挙（10 件まで）
        candidates = sorted(
            {
                r.get("question", "")
                for r in screened
                if r.get("data_source") == platform
            }
        )
        print(f"  ヒント: 該当プラットフォームのユニーク question 候補（先頭10件）:")
        for q in candidates[:10]:
            print(f"    - {q}")
        return 1

    print(f"\n[3/3] target_info.md 生成")
    md = build_target_info_md(prompt, platform, brand_name, target_resps)
    out_path = out_dir / "target_info.md"
    out_path.write_text(md, encoding="utf-8")
    print(f"  保存: {out_path}")
    print(f"  サイズ: {len(md)} chars")

    print(f"\n=== 完了 ===")
    print(f"次のアクション: Claude Code が {out_path.relative_to(common.PROJECT_ROOT)} を読んで検索意図を言語化")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Phase 4: 検索意図解釈 素材収集")
    p.add_argument("--brand-name", required=True)
    p.add_argument("--brand-url", required=True)
    p.add_argument("--prompt", required=True, help="対象プロンプト本文（CSV の Keyword 列と完全一致）")
    p.add_argument("--platform", required=True, choices=["chatgpt", "perplexity"])
    p.add_argument("--input-dir", default="input")
    args = p.parse_args()
    return run(
        brand_name=args.brand_name,
        brand_url=args.brand_url,
        prompt=args.prompt,
        platform=args.platform,
        input_dir=Path(args.input_dir),
    )


if __name__ == "__main__":
    sys.exit(main())
