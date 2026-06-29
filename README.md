# ahrefs-fanout-strategist

Ahrefs Brand Radarのクエリファンアウト機能とClaude Codeを組み合わせ、AI検索におけるコンテンツギャップを発見し、対策ページの構成案までを生成するClaude Code Skill。

## 何ができるか

1. 自社のビジネスモデルを調査し、競合候補を5社まで提案する
2. Brand Radarからファンアウトクエリを取得し、関連性のあるクエリだけにスクリーニングする
3. ファンアウトクエリから「AIがプロンプトをどう解釈しているか（検索意図）」を読み解く
4. 各クエリの言及率と引用元トップ10ページを取得する
5. 自社が言及されていないクエリに絞って、自社サイトに既存ページがあるかを確認する
6. 結果をCSVのマッピング表として出力する
7. 対策すべきクエリを1件選び、既存記事の改修提言または新規ページのブリーフをClaude Codeに生成させる

## 必要なもの

- Ahrefs契約（Brand Radarアドオン）
- Claude Code
- Google Custom Search APIキー

## セットアップ

### 1. リポジトリのクローンと依存インストール

```bash
git clone https://github.com/yuki-terayama/ahrefs-fanout-strategist.git
cd ahrefs-fanout-strategist
pip install -r requirements.txt
cp .env.example .env
```

### 2. Programmable Search Engine（PSE）の作成

site:検索で自社サイト内の既存ページを抽出するために、自社サイト用のPSEを1個作成します。

1. https://programmablesearchengine.google.com/ にアクセス
2. 「+ 追加」をクリック
3. 設定：
   - 検索エンジン名：任意（例：`my-site-search`）
   - 検索するサイト：**自社サイトのドメイン1個のみ**（例：`example.com`）
   - 言語：日本語
4. 「作成」をクリック
5. 作成後、ダッシュボードで **Search engine ID** をコピー

### 3. Google Custom Search API キーの発行

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. プロジェクトを選択または新規作成
3. [Custom Search API ライブラリ](https://console.cloud.google.com/apis/library/customsearch.googleapis.com) を開いて **有効にする**
4. [認証情報](https://console.cloud.google.com/apis/credentials) を開いて **+ 認証情報を作成 → APIキー**
5. 表示されたAPIキー（`AIza...`）をコピー

公式ドキュメント: [Custom Search JSON API](https://developers.google.com/custom-search/v1/introduction)

### 4. Ahrefs API キーの取得

[Ahrefs API キー管理画面](https://app.ahrefs.com/account/api-keys) で **API キーを発行**してコピー。

公式ドキュメント: [Ahrefs API v3 Brand Radar](https://docs.ahrefs.com/ja/api/reference/brand-radar)

### 5. .env ファイルにAPIキー類を記入

`.env` をエディタで開いて以下を設定：

```
AHREFS_API_KEY=（Step 4でコピーしたキー）
GOOGLE_CUSTOM_SEARCH_API_KEY=（Step 3でコピーしたAPIキー）
GOOGLE_CUSTOM_SEARCH_ENGINE_ID=（Step 2でコピーしたSearch engine ID）
```

### 6. スキルの登録

`SKILL.md` を `~/.claude/skills/ahrefs-fanout-strategist/` に配置するか、Claude Codeの設定でこのリポジトリをスキルとして登録してください。

## 使い方

Claude Codeで以下のように呼び出します：

```
/ahrefs-fanout-strategist
```

スキルが起動したら、対話形式で自社のドメインと競合候補を確定し、Phase 0〜9を順に進めます。

## ライセンス

MIT
