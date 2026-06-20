# 厳守ルールと致命的な落とし穴

AWS Blocks 特有で、知らないと事故る点を集約。各Blockの個別仕様は必ず同梱
`node_modules/@aws-blocks/blocks/docs/<package>.md` も併読すること。

## 1. Block ID の改名 = データ永久消失（最重要）
Block の第2引数（ID）は `scope/id` の `fullId` になり、それがAWSリソース名の素になる。
**IDを変えると次回デプロイで旧リソースが削除され新リソースが作られる** → `KVStore` /
`DistributedTable` / `Database` / `DistributedDatabase` / `FileBucket` などstateful Blockは
**保存データが永久に失われる**。
```ts
// デプロイ済み。これを 'todos' → 'todoItems' に変えると DynamoDB テーブルが作り直され全消去。
const todos = new DistributedTable(scope, 'todos', { /* ... */ });
```
**回避**: デプロイ後のIDは不変として扱う。表示名や変数名の変更はOKだが、第2引数の文字列は変えない。
どうしても変える必要があるならデータ移行（エクスポート→新Block→インポート）を設計する。

## 2. 認証は既定で全公開。ゲートは手動
`ApiNamespace` の各メソッドは**既定で誰でも呼べる**。認可は各メソッド内で `requireAuth()` /
`requireRole()` を**明示的に呼んで初めて**効く。書き忘れ＝認可漏れ。
```ts
export const api = new ApiNamespace(scope, 'api', (context) => ({
  async listMyTodos() {
    const user = await auth.getCurrentUser(context); // or auth.requireAuth(context)
    // user.userId でスコープする
  },
  async adminPurge() {
    await auth.requireRole(context, 'admin'); // これが無いと誰でも実行できてしまう
  },
}));
```
正確なメソッド名・gate関数は `docs/core.md` と `docs/bb-auth-*.md` を参照。

## 3. DSQL (`DistributedDatabase`) のparity限界
ローカルmockは **PGlite（WASM版の本物のPostgres）＋ DSQL検証層**。PGliteはフルPostgresなので、
DSQLの制約を**検証層が能動的に弾く**ことで本番との乖離を抑えている。

dev時にエラーになる（=mockがコピーできている制約）:
- 外部キー(`FOREIGN KEY`/`REFERENCES`)・`SERIAL`/`SEQUENCE`・トリガー・ビュー・PL/pgSQL・
  `TRUNCATE`・`LISTEN/NOTIFY`・拡張・`JSONB`カラム・RLS・一時テーブル・`COLLATE` 等は**非対応**。
- トランザクション: DDLとDML混在不可、1Tx=1DDLまで、**変異3,000行/Tx上限**。
- DDL(CREATE/ALTER/DROP)は**アプリランタイム不可**。マイグレーションファイルでのみ実行
  （本番のアプリLambdaは`dsql:DbConnect`のみ、マイグレーションLambdaが`dsql:DbConnectAdmin`を持つ、
  というIAM分離を再現している）。

**mockが再現できないもの（要注意）**:
- **OCC（楽観的同時実行制御）の競合は自然には起きない**（PGliteは単一接続）。`40001`
  serialization failure をテストするには `simulateConflict()` を使う。`transactionWithRetry`
  （`retryOnConflict`）のリトライ実装は確認できるが、本当の競合検知は実機でのみ。
- ASYNCインデックスの可視化タイミング・分散コミットのレイテンシ・性能特性。

**結論**: スキーマ/構文レベルはローカルで十分検証できる。**同時実行・分散の実挙動は
`npm run sandbox` で実機検証する。** SQLの使い分け（DSQL vs フルPostgresの`Database`）は
`docs/index.md` の「Choosing a data block」に従う。

## 4. `--conditions=cdk` を外すと mock が混入する
CDK synth時に `cdk` condition が無いと、Blockが**mock実装のまま synth され**、意図しない
（あるいは空の）インフラが生成される。フレームワークは `assertCdkConditionActive()` で
これを検知して例外を投げる。
- **必ず `npm run sandbox` / `npm run deploy` を使う**（`NODE_OPTIONS=--conditions=cdk` を自動設定）。
- 素の `npx cdk synth/deploy` を直接叩く必要がある場合は `NODE_OPTIONS="--conditions=cdk"` を付ける。
- Lambdaバンドルは別途 esbuild が `--conditions aws-runtime` を付ける（自前バンドル設定を上書きしない）。

## 5. 永続化に「素のローカル手段」を使わない
ローカル配列・`fs`での自前ファイル・別のローカルDBを使うと、デプロイ時にAWSへ繋がらない。
**永続化は必ずBlockで行う**（mockがローカル動作を担うので、同じコードがそのままデプロイできる）。
キャッシュ的な一時メモリでも、共有状態なら `KVStore` を使う。

## 6. JSON-RPCは透過。型はフロントまで伝播
APIの呼び出しは型付きクライアントで直接行う。RPCのURL構築・ペイロード手組み・`fetch`直叩きを
しない。バックエンドのメソッドシグネチャを変えると、フロントが即コンパイルエラーになる
（コード生成ステップが無いのが強み）。デバッグで接続確認したいときだけ例外的にcurl可。

## 7. その他よくある詰まり
- **`.bb-data/` はローカルmockの実データ**。消すとローカルの保存内容が消えるが、本番には無関係。
- **`Database`（Aurora Serverless v2）はアイドルコスト/コールドスタートあり**（最低0.5 ACU）。
  単純なPostgres互換で良ければ `DistributedDatabase`（DSQL, アイドル0）を優先。
- **既存リソースの取り込み**は `fromExisting()` 系（例: 既存Postgres、既存テーブル）。詳細は各doc。
