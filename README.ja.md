---
lang: ja
source: README.md
source_sha: e45d135114fe4688933c79c4eab4a34aa28ba3c9
---

> 📖 これは [README.md](README.md) の日本語訳です。**正典は英語版**で、差異がある場合は英語が優先されます。
> このファイルは AI には読み込まれません（人間の読者・保守者向け）。

# aws-blocks-skills

コーディングエージェントが **AWS Blocks** のバックエンドを正しく・速く作れるよう支援する
[Skill](https://docs.claude.com/en/docs/claude-code/skills) です。正しいメンタル
モデルを与え、フレームワーク同梱のドキュメントへ誘導し、データ消失やデプロイ失敗を招く落とし穴を
未然に防ぎます。

## AWS Blocks とは？

[AWS Blocks](https://docs.aws.amazon.com/blocks/latest/devguide/what-is-blocks.html) は「AWS 上で
フルスタックアプリを構築するためのバックエンドツールキット」です。各 Block（`KVStore`,
`DistributedTable`, `FileBucket`, `AuthCognito`, `Realtime`, `Agent` など）は自己完結したバックエンド
機能で、アプリコード・ローカル開発環境・実行に必要な AWS インフラを一体で持ちます。必要な Block を
組み合わせると、AWS Blocks が AWS のベストプラクティスに沿ってインフラを自動定義します。

核心は、Node.js の conditional exports による **1つのコード・3つの解決** です。`new
DistributedTable(scope, 'todos', {...})` という同じ1行が、開発ではローカルのメモリ/ファイル mock として
動き、デプロイ時には CDK construct（実 DynamoDB 等）になり、Lambda では AWS SDK を呼びます。「AWS
アカウントなしでアプリ全体がローカルで動き……同じコードを変更せずに AWS へデプロイできる」のが特徴です。

## このスキルがすること

フレームワークは正典ドキュメントを npm パッケージに同梱済みです。このスキルはその上に乗る **薄い操舵
レイヤー＋ルーター** であり、あえて API リファレンスにはしていません（インストール済みバージョンから
乖離しないため）。具体的には:

- **正しいメンタルモデルを与える** — なぜ同じコードが3通りに解決されるのか、IFC 層 / `Scope` /
  `fullId` とは何か、なぜそれが重要か。
- **同梱ドキュメントへ誘導する** — Block 個別の正確な API は
  `node_modules/@aws-blocks/blocks/docs/<package>.md` にあり、常にインストール済みバージョンと一致する。
  スキルは写しを持たず、そこへ案内する。
- **致命的な落とし穴を未然に防ぐ**:
  - ⚠️ Block ID の改名＝リソース再作成＝stateful Block では **データ永久消失**。
  - ⚠️ API は **既定で全公開** — 認可は `requireAuth()` / `requireRole()` を呼んで初めて効く。
  - ⚠️ DSQL（`DistributedDatabase`）の parity 制約と、同時実行は実機検証が必要な理由。
  - ⚠️ `--conditions=cdk` を外すと mock が CDK synth に混入する。
- **適切な Block を選ぶ** — 「やりたいこと」から Block とそのドキュメントへ導くルーティング表
  （例: 構造化データ → `DistributedTable`、サーバーレス SQL → `DistributedDatabase`）。

結果として、エージェントは AWS Blocks 上で一発で正しく構築でき、正確な API は同梱ドキュメントを参照
するようになります。

## いつ起動するか

プロジェクトが AWS Blocks を使っているとき、Claude が自動でこのスキルを起動します — `aws-blocks/`
ディレクトリ、`@aws-blocks/*` からの import、`DistributedTable` / `ApiNamespace` /
`npm run dev/sandbox/deploy` などの言及が合図です。トリガーの全リストは
[`skills/aws-blocks/SKILL.md`](skills/aws-blocks/SKILL.md) の `description` を参照してください。

## スキル一覧

| スキル | 何を助けるか |
|---|---|
| [`aws-blocks`](skills/aws-blocks/SKILL.ja.md) | `@aws-blocks/*` フレームワークでバックエンドを構築: 適切な Block 選定、ローカル → サンドボックス → 本番のワークフロー、データ消失 / 認可 / DSQL / `--conditions` の落とし穴回避。 |

## リポジトリ構成

```
skills/
  aws-blocks/
    SKILL.md            # スキル本体（操舵レイヤー＋ルーター）
    references/         # mental-model, rules-and-gotchas, workflow-troubleshooting, best-practices
    evals/evals.json    # トリガー/挙動の評価ケース
scripts/
  check-i18n.sh         # 英語 → 日本語の翻訳ドリフト検出
  check-upstream-docs.py  # 上流 AWS ドキュメントのドリフト検出
  upstream/             # manifest.json ＋ snapshots/（最後にレビューした上流コンテンツ）
.github/workflows/check-upstream-docs.yml  # 週次の上流ドリフトチェック
.claude/commands/refresh-best-practices.md # AI アシスト反映の runbook
```

## ドキュメントの言語

スキルは **英語**（AI が読み込む正典）で出荷し、日本語話者が快適に読めるよう **日本語コンパニオン**
（`*.ja.md`）を併記します。英語が正典です。各 `*.ja.md` は frontmatter に英語ソースの
`git hash-object` を記録するため、`scripts/check-i18n.sh` が古くなった（ドリフトした）翻訳を検出します。

## コンテンツの鮮度維持

2 つのドリフト検出器がこのスキルを同期させます。どちらも「基準ハッシュを記録し、変化したら知らせる」という
同じ発想で作られています:

1. **翻訳ドリフト** — `scripts/check-i18n.sh` は各 `*.ja.md` に記録された `source_sha` を、英語ソースの
   現在の `git hash-object` と比較します。終了コード 0 = すべて同期済み。
2. **上流ドキュメントドリフト** — `scripts/check-upstream-docs.py` は、一部のスキル内容の元になっている
   上流 AWS ドキュメント（現在は
   [Best practices ページ](https://docs.aws.amazon.com/blocks/latest/devguide/best-practices.html)）を
   追跡します。各ページを再取得し、本文を正規化して、その sha256 を
   `scripts/upstream/manifest.json` の基準値と比較します。`scripts/upstream/snapshots/` に保存した
   スナップショットにより、**何が変わったかの diff** を表示できます。週次の GitHub Actions ワークフロー
   （`.github/workflows/check-upstream-docs.yml`）がこれを実行し、変化時に `upstream-drift` ラベルの
   Issue を起票します。

`best-practices.md` は Web ページをコピーせず、あえて SDK 同梱ドキュメントへ**ルーティング**する設計
（矛盾時は同梱ドキュメントが優先）のため、上流変更の反映はコピー作業ではなく判断作業です。ドリフト検知時は
Claude Code で **`/refresh-best-practices`** を実行します。diff を読み、本当に新規の横断的指針だけを反映し、
スナップショットを再ベースライン（`python3 scripts/check-upstream-docs.py --update`）し、それに伴う翻訳
ドリフトも修正します。
