---
lang: ja
source: SKILL.md
source_sha: a8b455f5001d57d842c93cdfddaf30eb8a3452fc
---

> 📖 これは [SKILL.md](SKILL.md) の日本語訳です。**正典は英語版**で、差異がある場合は英語が優先されます。
> このファイルは AI には読み込まれません（人間の読者・保守者向け）。

# AWS Blocks 実装ガイド（操舵レイヤー）

AWS Blocks は `@aws-blocks/*` の TypeScript「Infrastructure from Code」フレームワーク。
このSkillは **薄い操舵レイヤー＋ルーター** です。APIリファレンスは持ちません。
**正典はSDKに同梱されたドキュメント**（`node_modules/@aws-blocks/blocks/docs/`）にあり、それは
インストール済みバージョンと常に一致します。このSkillの役割は、(1)正しいメンタルモデルを与え、
(2)同梱docsへ誘導し、(3)致命的な落とし穴を未然に防ぐことです。

## ワンライナーのメンタルモデル
あなたが書く `new DistributedTable(scope, 'todos', {...})` という**同じ1行**が、Node.jsの
conditional exports によって実行コンテキストごとに**別の実装**へ解決される:

| コンテキスト | 解決される実装 | 振る舞い |
|---|---|---|
| ローカル開発 `npm run dev` | mock（メモリ＋`.bb-data/`のJSON/PGlite） | AWS不要・オフライン |
| CDK synth `npm run deploy/sandbox` | CDK construct | DynamoDB等のリソースを定義 |
| Lambda 実行（本番） | AWS SDK 呼び出し | 実サービスへアクセス |

コードは1つ。書き換え不要。詳細は [references/mental-model.ja.md](references/mental-model.ja.md)。

## 最重要ルール（必ず守る）
1. **Blockを使う前に、その同梱docを必ず読む。** API・オプション・ローカル挙動・本番挙動・
   ベストプラクティスが各ページに揃っている。場所:
   `node_modules/@aws-blocks/blocks/docs/<package>.md`
   （見つからなければ `find . -path '*@aws-blocks/blocks/docs/index.md' -not -path '*/.git/*'` で探す）。
2. **永続化・クラウド抽象は必ず Building Block で行う。** ローカル配列・自前のファイル・
   別のローカルDBを使わない（mockがその役割を担うため、Blockを使えばそのままAWSにデプロイできる）。
3. **JSON-RPCトランスポートは透過。** RPCペイロードを手で組まない。型付きAPIを
   `import { api } from 'aws-blocks'` で直接呼ぶ。バックエンドの型がフロントまで自動で伝播する
   （コード生成ステップは無い）。

## Block選定のルーティング（必ずこの順で）
1. まず **決定木** を読む → `node_modules/@aws-blocks/blocks/docs/index.md`
   （「何をしたいか」から適切なBlockを選ぶカタログ＋キーワード）。
2. 次に **個別doc** を読む → `node_modules/@aws-blocks/blocks/docs/<package>.md`。
3. 横断的なコア概念（`Scope` / `ApiNamespace` / `withAuth` / `RawRoute` / CORS / JSON-RPC）は
   → `node_modules/@aws-blocks/blocks/docs/core.md`。
4. 全体ガイド（アーキテクチャ・よくある間違い）は → `node_modules/@aws-blocks/blocks/README.md`。

主なBlockと用途（詳細は必ず上記docへ）:

| やりたいこと | Block | 同梱doc |
|---|---|---|
| キーバリュー（キャッシュ/フラグ） | `KVStore` | bb-kv-store.md |
| 構造化データ＋索引＋クエリ（**データの既定**） | `DistributedTable` | bb-distributed-table.md |
| サーバーレスSQL（基本のPostgres互換） | `DistributedDatabase` (Aurora DSQL) | bb-distributed-data.md |
| フルPostgres（FK/RLS/トリガー/大トランザクション） | `Database` (Aurora Serverless v2) | bb-data.md |
| ファイル/アップロード | `FileBucket` | bb-file-bucket.md |
| 認証（プロトタイプ/本番/OIDC） | `AuthBasic` / `AuthCognito` / `AuthOIDC` | bb-auth-*.md |
| WebSocket pub/sub | `Realtime` | bb-realtime.md |
| 背景ジョブ / 定期実行 | `AsyncJob` / `CronJob` | bb-async-job.md / bb-cron-job.md |
| AIエージェント / RAG | `Agent` / `KnowledgeBase` | bb-agent.md / bb-knowledge-base.md |
| メール / 設定値 / 可観測性 | `EmailClient` / `AppSetting` / `Logger`等 | bb-email-client.md ほか |

**データBlockの選び方**: 既定は `DistributedTable`。複数レコードをまたぐJOIN・多次元フィルタ・
トランザクション・SQLの柔軟性が要るときだけSQL系へ。SQLが要るなら原則 `DistributedDatabase`
（DSQL、アイドルコスト0）。FK/RLS/トリガー/3,000行超トランザクション/既存Postgres統合が必要な
ときだけ `Database`（Aurora Serverless v2、最低0.5 ACUのアイドルコスト or コールドスタート有り）。

## 致命的な警告（インライン。詳細は rules-and-gotchas.ja.md）
- ⚠️ **Block ID（コンストラクタ第2引数）の改名 = リソース削除・再作成 = stateful Blockは
  データ永久消失。** ID はデプロイ後は不変として扱う。
- ⚠️ **認証は既定で全API公開。** ゲートは各メソッド内で `requireAuth()` / `requireRole()` を
  明示的に呼んで初めて効く。書き忘れ＝認可漏れ。
- ⚠️ **DSQL(`DistributedDatabase`)はDDL不可・FK不可・JSONB不可等の制約あり。** mockはこれらを
  dev時に弾くが、**OCC（楽観的同時実行）競合は自然には起きない**ので `simulateConflict()` で
  テストし、最終的に `npm run sandbox` で実機検証する。
- ⚠️ **`--conditions=cdk` を外すと mock が CDK synth に混入する。** 必ず `npm run sandbox/deploy`
  を使う（これらが `NODE_OPTIONS=--conditions=cdk` を自動設定する）。素の `cdk synth` を直接叩かない。

詳細・回避法・最小コード例 → [references/rules-and-gotchas.ja.md](references/rules-and-gotchas.ja.md)

## 開発ワークフロー（詳細は workflow-troubleshooting.ja.md）
| コマンド | 何が起きるか |
|---|---|
| `npm run dev` | 全Blockがmockでローカル起動（`.bb-data/`に永続化）。AWS不要・ホットリロード |
| `npm run test:e2e` | 型付きクライアントでe2e。dev未起動なら自動起動 |
| `npm run sandbox` / `npm run sandbox:destroy` | 実AWSへ高速デプロイ（Lambdaホットスワップ）/ 撤去 |
| `npm run deploy` / `npm run destroy` | 本番フルデプロイ（CloudFormation）/ 撤去 |

高速反復: `npm run dev &` を背景起動し `npm run test:e2e` を反復（毎回サーバ再利用）。
**APIへ curl/fetch を直接投げない**（接続トラブル調査時を除く）。型付きAPIを直接呼ぶ。
詳細・症状→原因→修正表 → [references/workflow-troubleshooting.ja.md](references/workflow-troubleshooting.ja.md)

## バックエンドの形（IFC層）
バックエンドは `aws-blocks/index.ts` 1ファイルに集約される（= IFC層）。ここでBlockを
インスタンス化し、`ApiNamespace` でAPIを定義し、`export` する。フロント(`src/`)は
`import { api } from 'aws-blocks'` でそれを型安全に呼ぶ。CDK定義は任意の `aws-blocks/index.cdk.ts`
（`BlocksStack.create({ backendCDKPath: './index.ts', ... })`）で、これも同じ `index.ts` を
`cdk` condition で読み直してインフラを導出する。

## ベストプラクティス（同梱版を読む。ここでの追加は少数）
ベストプラクティスの大半は**SDKに同梱**されインストール済みバージョンと一致する — それを読み、再発明しない:
`README.md` の **## Best practices** / **## Common mistakes** / **## Testing** / **Adding auth and data**、
`docs/core.md`（`ApiError`/`isBlocksError` によるエラー処理、認証は既定で公開）、`docs/index.md`
（Block選定）、各 `docs/<block>.md` の **## Best Practices** / **## Scaling & Cost**。ここに複製すると
バージョン乖離を招く（例: 公開Webページの「1つの `KVStore` をキープレフィックスで分割」は同梱の
`bb-kv-store.md`「インスタンス1つに論理エンティティ1つ」と矛盾する。同梱docに従う）。

同梱docが述べていない横断的な実践だけ → [references/best-practices.ja.md](references/best-practices.ja.md):
- アプリ1つに `Scope` は1つ。`index.ts` は薄く保ち業務ロジックは別モジュールへ抽出（mock Blockでの純粋
  関数の単体テストも可能になる）。
- dev/staging/prodでAWSアカウントを分け、環境固有設定（ドメイン・VPC・WAF・CORS）は実行時コードでなく
  `index.cdk.ts` に置く。
- 記述的なBlock IDとAPIメソッドのJSDocがAIコーディングエージェントに良いコンテキストを与える。

## 参照ファイル（必要に応じて読む）
| ファイル | いつ読むか |
|---|---|
| [references/mental-model.ja.md](references/mental-model.ja.md) | conditional exportsの2階層・切替スイッチ・なぜ壊れるかを理解したいとき |
| [references/rules-and-gotchas.ja.md](references/rules-and-gotchas.ja.md) | データ消失/認可/DSQL/conditionsの落とし穴を避けたいとき（実装前に一読推奨） |
| [references/workflow-troubleshooting.ja.md](references/workflow-troubleshooting.ja.md) | コマンド・環境差・e2eループ・エラー解決をしたいとき |
| [references/best-practices.ja.md](references/best-practices.ja.md) | ベストプラクティスの各トピックを正典の同梱ロケーションへ辿りたいとき＋少数の横断的な追加分 |

そして忘れずに: **個別Blockの正確なAPIは、常に同梱の
`node_modules/@aws-blocks/blocks/docs/<package>.md` を参照すること。** このSkillはそこへの
案内役であり、APIの写しは持たない（バージョン不一致を避けるため）。
