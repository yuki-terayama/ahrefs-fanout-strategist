---
name: ahrefs-fanout-strategist
description: Ahrefs Brand Radarのクエリファンアウト機能と Claude Code を組み合わせ、AI検索（ChatGPT・Perplexity）における自社のコンテンツ対応状況を可視化し、対策ページの既存改修提言または新規ブリーフまで一気通貫で生成する。「ファンアウトクエリ分析」「Brand Radar活用」「AEOコンテンツギャップ」等の依頼で起動。
---

# ahrefs-fanout-strategist

Ahrefs Brand Radar のクエリファンアウト機能と Claude Code を組み合わせ、AI検索における自社のコンテンツ対応状況を可視化し、対策ページの構成案までを生成するスキル。

データ取得は **API モード**（Brand Radar API 直接）か **CSV モード**（UIエクスポート CSV 読込）の2モード。API ユニットが足りない場合は CSV モードに切り替え可能。

---

## Phase 0: スキル起動時のユーザー指定（対話フロー）

スキルが起動したら、Claude Code は **最初に必ず以下3点をユーザーに質問** し、確定してから次のフェーズに進む。

### 起動時の対話テンプレート

スキル起動時、Claude Code は以下のメッセージをユーザーに送る：

> このスキルを開始します。最初に以下の3点を教えてください。
>
> **1. 自社サイトの URL**（例: `ahrefs.com`）
>
> **2. 競合5社**：Ahrefs Brand Radar の検索画面で **自社 URL だけを入力** すると、競合候補が自動抽出されます。そのスクリーンショットを共有してください。必要なら追加・削除・差し替えてください。
>
> **3. 自社の事業情報**：
>   - 業界
>   - 主要製品・サービス（箇条書き）
>   - ターゲット顧客

1〜3 が揃うまで Phase 2 以降に進まない。質問は3つまとめてでも、1→2→3 と順にでもよい（ユーザーの応答ペースに合わせる）。

---

### 各情報の扱い

#### 1. 自社サイトの URL
- ドメイン部分（例: `ahrefs.com`）を `--brand-url` に渡す
- ブランド名（言及判定キーワード）は URL から推定（例: `ahrefs.com` → `Ahrefs`）し、ユーザーに簡単に確認

#### 2. 競合5社（Brand Radar UI の自動抽出を活用）

Ahrefs Brand Radar の検索画面では、**URL を入力するだけで競合候補を自動抽出してくれる**（ブランド名指定は不要）。

手順：
1. Brand Radar の検索画面で **自社 URL だけ** を入力
2. 競合候補が自動表示される
3. **そのスクリーンショットを Claude にチャットで共有**
4. ユーザーが必要に応じて追加・削除・差し替え
5. 確定した5社を `output/competitors.json` に保存

#### 3. 自社の事業情報

Phase 3 の関連性スクリーニングで使う判定基準を、ユーザーがチャットで指定。
`output/business_info.md` に保存（ユーザー指定そのまま）。

### 出力ファイル

`output/competitors.json`:
```json
[
  {"name": "Semrush", "domain": "semrush.com"},
  {"name": "ubersuggest", "domain": "neilpatel.com"}
]
```

`output/business_info.md`:
```markdown
# {社名} の事業情報（ユーザー指定）
- ドメイン: ...
- 業界: ...
- 主要製品・サービス:
  - ...
- ターゲット顧客:
  - ...
```

---

## Phase 1: Brand Radar 設定

- **API モード**: Phase 0 の競合リストをそのまま API に渡す → UI 設定不要
- **CSV モード**: ユーザーが Brand Radar UI で自社+競合を設定し、直近7日分の CSV をエクスポート → `input/` に配置（UTF-16 TSV 形式）

---

## Phase 2: データ取得

### API モード（Brand Radar API 直接）

```bash
python scripts/main.py --source api \
    --brand-name "Ahrefs" --brand-url "ahrefs.com" \
    --competitors-file output/competitors.json \
    --days 7
```

- 7日分の AI 応答を取得（`brand-radar/ai-responses`、POST + 構造化リクエスト）
- ChatGPT + Perplexity、日本ロケーション
- 推定消費ユニット: 約 40,000〜45,000 ユニット/週（149件/日 × 41ユニット × 7日）

### CSV モード（UIエクスポート読込）

```bash
python scripts/main.py --source csv \
    --brand-name "Ahrefs" --brand-url "ahrefs.com"
```

- `input/` 配下の全 CSV を読み込み
- 同一応答（`question × data_source × last_updated`）は重複除去
- API ユニット節約・確実な取得が必要なときに使用

---

## Phase 3: スクリーニング

### 3a. 競合名スクリーニング（main.py内部で自動実行）

プロンプトに競合名（フルネーム or 短縮形）が含まれているものを除外。

### 3b. ビジネスモデル関連性スクリーニング（Claude Code 対話）

main.py の出力からユニーク question 一覧を取得し、Claude が Phase 0 のビジネスモデルに照らして判定：

- **除外する**:
  - 情報意図系（「〜とは何」「違いは」「なぜ」「やり方」「手順」）
  - サービス推薦系で自社が**ツール会社**の場合: コンサル・代理店・業者・外注・SEO会社の質問
  - 微妙な境界判断
  - 全く別業界の質問
- **残す**:
  - 自社が直接競合し得るツール推薦系（「おすすめツール」「無料ツール」「ランキング」など）
  - 方法論クエリでも他社（観測対象ブランドのいずれか）がメンションされているもの

結果を `output/relevant_questions.txt`（1行1プロンプト）に保存。

その後、main.py を以下のように再実行：

```bash
python scripts/main.py --source csv \
    --brand-name "Ahrefs" --brand-url "ahrefs.com" \
    --include-only-file output/relevant_questions.txt \
    --site-search-limit 0
```

---

## Phase 4: 検索意図解釈（オンデマンド、Phase 9 に統合）

全ファンアウトクエリで事前生成する**運用ではなく**、Phase 8 で対策クエリが1件選ばれた後、Phase 9 の最初のステップとして Claude がそのクエリだけ検索意図解釈を生成する。

理由：
- 対策しないクエリの解釈は読まれない → 事前生成は無駄
- 1件に絞れば深く解釈できる → 対策提言の質が上がる

### 素材収集スクリプト

```bash
python scripts/phase4_intent.py \
    --brand-name "Ahrefs" --brand-url "ahrefs.com" \
    --prompt "無料のSEO分析ツールは？" \
    --platform "perplexity"
```

出力: `output/phase4/{slug}/target_info.md`

### 検索意図解釈のロジック

**ファンアウトクエリの語のみ** を見て解釈する。応答本文は使わない
（応答本文は AI が組み立てた答えであり、ユーザーの需要の証拠ではない）。

手順:
1. ファンアウトクエリの語を機械的に分解
2. 各語を「直訳語」か「幅あり語」に分類
3. 直訳語 → 1つに確定して変換
4. 幅あり語 → **絞り込まず、主要候補を列挙したまま残す**
5. 合成して1文で表現（幅あり語は「○○ / △△ / □□ などのいずれか or 複数」と書く）
6. 単語変換表（語 / 種別 / 解釈 or 候補）を併記

NG:
- 解釈幅のある語を1つの候補に決め打ちする（→ 主要候補を列挙したまま残す）
- ファンアウトクエリに登場しない要素（想定読者層・推奨スタンス・カバレッジ軸・優先順位など）を後付けで追加する
- 応答本文の見出し構造・列挙順・語彙を解釈の根拠に使う（応答は AI の「答え」であり需要の証拠ではない）

### 例

ファンアウトクエリ: `無料のSEO分析ツールは？`

| 語 | 種別 | 解釈 / 候補 |
|---|---|---|
| 無料 | 直訳 | 予算ゼロで |
| SEO | 直訳 | 検索エンジン最適化のために |
| 分析 | 幅あり | 自社サイト診断 / 競合分析 / キーワード分析 / 順位分析 / 被リンク分析 などのいずれか or 複数 |
| ツール | 直訳 | ツールが欲しい |

解釈: 予算ゼロで使える、SEO の何らか（自社サイト診断・競合分析・キーワード調査・順位調査・被リンク分析 など）ができるツールを探している。

マッピング表の「検索意図」列はオンデマンド生成のため、対策しなかったクエリは空欄のまま。

---

## Phase 5: 集計（main.py内部で自動実行、プラットフォーム別）

集計キーは `(question, data_source)`。同じプロンプトでも ChatGPT と Perplexity でファンアウトクエリ・言及・引用元が異なるため、別行として集計。

- 言及率: Mentions 列（CSV）または response 本文（API）で判定。表記は `言及数 / 総応答数`
- 引用元: Cited pages を出現回数順に全件、`URL（×N）` 形式で表示

---

## Phase 6: site:検索（main.py内部で自動実行、Playwright）

言及なし `(question, platform)` 全件について：

1. ファンアウトクエリを取得（空ならプロンプト本文を使用）
2. Playwright で `site:{自社ドメイン} {クエリ}` を Google 検索
3. 最大3回リトライ、結果統合で上位3件を抽出

初回は Google の CAPTCHA が出る場合がある（手動で通す。Cookie 永続化で2回目以降は自動）。

---

## Phase 7: マッピング XLSX 出力（main.py内部で自動実行）

`output/mapping_{domain}_{timestamp}.xlsx` に出力。言及率昇順、12列構成。

| # | 列名 |
|---|---|
| 1 | プラットフォーム |
| 2 | プロンプト |
| 3 | ファンアウトクエリ（直近） |
| 4 | 検索意図（AI解釈） |
| 5 | 言及（あり / 総応答） |
| 6 | 引用元URL（多い順） |
| 7-8 | site:1位 URL / タイトル |
| 9-10 | site:2位 URL / タイトル |
| 11-12 | site:3位 URL / タイトル |

---

## Phase 8: 対策クエリの選択（Claude Code 対話）

ユーザーが XLSX を見て、マッピング表から **1件** 対策するクエリを選ぶ。

---

## Phase 9: 深掘り分析と提言生成（Claude Code 対話）

選ばれたクエリに対して以下を実行：

1. **検索意図の解釈**：ファンアウトクエリの語のみから AI のプロンプト解釈を Claude が言語化
2. **引用元トップ5の本文を WebFetch / Playwright で取得**（取得失敗のページは警告を出してスキップ）
3. **site:検索結果がある場合、自社既存ページの本文も WebFetch / Playwright で取得**
4. **Claude が本文ベースで判断**（2軸で評価）:

   **軸1: ページ種別の一致性**
   - 引用元のページ種別と自社既存ページの種別を比較
   - 主な種別: 機能一覧/製品LP / 記事タイプ（解説・比較・選び方） / FAQページ / ランキング・比較表ページ / ハブページ（リンク集）
   - 種別不一致の場合、既存ページに引用元の内容を移植すると本来目的が壊れる → **新規作成原則**

   **軸2: 内容のカバレッジ**
   - 既存ページが検索意図のカバー範囲を満たしているか
   - 大改修が必要なレベルで不足 → **新規作成**
   - 部分追加で済むレベル → **既存改修**

   両軸を組み合わせて判断:
   - 種別一致 × カバレッジ部分不足 → **既存改修ルート**
   - 種別不一致（または既存ページなし）→ **新規作成ルート**
   - 種別一致 × カバレッジ大幅不足 → 個別判断（新規が原則だが既存を活かす選択肢も検討）

5. **ルート別に提言を生成**（検索意図解釈・ページ種別判定・カバレッジ評価を根拠として明記）
6. **md 形式で `output/proposal_{slug}_{timestamp}.md` に保存** + **Claude Code 内に同内容を直接出力**（必須。md 保存のみで終わらせない）

### 既存改修ルートの提言フォーマット

```markdown
# 既存改修提言: {クエリ}

## 対象URL
## 現状サマリ
## 引用元トップ5との内容ギャップ
  - 構造のギャップ
  - カバレッジのギャップ
  - データ・事例のギャップ
## 追加すべきセクション（h2/h3案）
## 強化すべき既存セクション
## 削除・整理を検討すべき情報
## 構造化データ・スキーマの推奨
## 公開後の検証ポイント
```

### 新規作成ルートのブリーフフォーマット

```markdown
# 新規ページブリーフ: {クエリ}

## ページタイトル案（3案）
## メタディスクリプション案
## ページタイプ（記事/比較表/ランディング/FAQ）
## 想定URLパス
## ターゲット読者
## 想定文字数
## 構成案（h1〜h3）
## 各セクションで触れるべきポイント
## 引用元から学ぶべき要素（URL+該当箇所引用）
## 構造化データ・スキーマの推奨
## 公開後の検証ポイント
```

---

## 設定ファイル

### `.env`
```
AHREFS_API_KEY=（Ahrefs API キー）
```

### `output/competitors.json`（Phase 0 で生成）
```json
[
  {"name": "Semrush", "domain": "semrush.com"},
  ...
]
```

### `output/relevant_questions.txt`（Phase 3 で生成）
```
無料のSEO分析ツールは？
お金をかけずにできるSEO対策は？
```

### `output/intents.json`（Phase 4 で生成、任意）
```json
{
  "無料のSEO分析ツールは？": "予算をかけずにSEO診断したい初心者ユーザー",
  ...
}
```

---

## ファイル構成

```
ahrefs-fanout-strategist/
├── README.md
├── SKILL.md (この文書)
├── LICENSE
├── .env / .env.example
├── requirements.txt
├── input/                      # CSV モード時の入力
├── output/                     # 中間ファイル・XLSX・提言 md
└── scripts/
    ├── main.py                 # エントリーポイント
    └── lib/
        ├── common.py
        ├── brand_radar.py      # Ahrefs Brand Radar API ラッパー
        ├── csv_loader.py       # CSV UI エクスポート読込
        ├── aggregation.py      # プラットフォーム別集計
        ├── web_search_playwright.py  # Playwright site:検索
        └── xlsx_export.py
```
