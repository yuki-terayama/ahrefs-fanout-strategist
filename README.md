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

```bash
git clone https://github.com/clearyst-inc/ahrefs-fanout-strategist.git
cd ahrefs-fanout-strategist
pip install -r requirements.txt
cp .env.example .env
# .env を編集してAPIキーを設定
```

その後、`SKILL.md` を `~/.claude/skills/ahrefs-fanout-strategist/` に配置するか、Claude Codeの設定でこのリポジトリをスキルとして登録してください。

## 使い方

Claude Codeで以下のように呼び出します：

```
/ahrefs-fanout-strategist
```

スキルが起動したら、対話形式で自社のドメインと競合候補を確定し、Phase 0〜9を順に進めます。

## ライセンス

MIT
