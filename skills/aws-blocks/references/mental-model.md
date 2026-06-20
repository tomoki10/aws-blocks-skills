# メンタルモデル: AWS Blocks はどう「同じコード」を3面に解決するか

このページは「なぜそう動くのか／なぜ壊れるのか」を理解するための土台。実装時の細かいAPIは
同梱docs（`node_modules/@aws-blocks/blocks/docs/`）を見ること。

## 核心: Node.js の Conditional Exports
仕組みの本体は魔法でもコード生成でもなく、`package.json` の `exports` フィールドの **condition**。
同じ `import` 文が、解決時のconditionによって**物理的に別ファイル**へ向く。これが2階層ある。

### 階層1: フロントエンド ↔ バックエンド の分離（プロジェクトの aws-blocks ワークスペース）
`aws-blocks/package.json` の `exports`:
- `browser` / `react-server` / `import` → `./client.js`（自動生成の型付きRPCクライアント。`src/`が使う）
- `types` / `default` → `./index.ts`（バックエンド実装そのもの。dev server / Lambda が使う）

→ だから `src/` が `import { api } from 'aws-blocks'` するとクライアントを、サーバ側が同じ名前で
importすると実装を得る。**コード生成なしで型が一致する**仕組みの土台。`client.js` は
dev server / build が `index.ts` の export を見て自動再生成する（手で編集しない）。

### 階層2: local / cdk / aws-runtime の分離（各Blockパッケージ）
例: `@aws-blocks/bb-distributed-table/package.json` の `exports`:
```json
"exports": { ".": {
  "browser":     "./dist/index.browser.js",
  "cdk":        { "types": "./dist/index.cdk.d.ts", "default": "./dist/index.cdk.js" },
  "aws-runtime": "./dist/index.aws.js",
  "types":       "./dist/index.mock.d.ts",
  "default":     "./dist/index.mock.js"
}}
```
| condition | 解決先 | 中身（同じpublic API・異なる実装） |
|---|---|---|
| `default`（条件指定なし） | `index.mock.js` | メモリ＋`.bb-data/*`へ永続化。ローカル開発用 |
| `cdk` | `index.cdk.js` | `aws-cdk-lib`の`Table`を生成し`grantReadWriteData()`。get/put等は synthGuard スタブ |
| `aws-runtime` | `index.aws.js` | `DynamoDBDocumentClient`で実DynamoDBへCRUD。本番Lambda用 |
| `browser` | `index.browser.js` | クライアント側スタブ |

3ファイルとも**同一のpublic API**を持つので、`index.ts` 側のコードは1つで済む。

## condition を切り替える「スイッチ」（実装の所在）
| コンテキスト | スイッチ | 所在 |
|---|---|---|
| ローカル開発 `npm run dev` | `tsx watch`（**conditionなし**）→ `default` = mock | ルート `package.json` の `dev` script |
| CDK synth `npm run sandbox`/`deploy` | `NODE_OPTIONS="--conditions=cdk"` ＋ `cdk.json` の `npx tsx -C cdk ...` → `cdk` | `@aws-blocks/core/dist/scripts/sandbox.js`・`deploy.js`、`cdk.json` |
| Lambda バンドル | esbuild `--conditions aws-runtime` → `aws-runtime` | `@aws-blocks/core/dist/cdk/blocks-backend.js` |
| 取りこぼし防止 | `assertCdkConditionActive()` が `--conditions=cdk` 欠落時に throw（mockを誤ってsynthするのを防止） | 同 `blocks-backend.js` |

CDKエントリの連結: `cdk.json` → `aws-blocks/index.cdk.ts` の
`BlocksStack.create({ backendCDKPath: index.ts, backendHandlerPath: index.handler.ts })`。
つまり **CDK層は同じ `index.ts` を `cdk` condition で読み直して** インフラを導出し、
`index.handler.ts`（`createLambdaHandler(() => import('./index.js'))`）が本番runtimeのエントリになる。

## IFC層・Scope・fullId
- **IFC層 = `aws-blocks/index.ts`**: Blockのインスタンス化とAPI定義を1ファイルに集約。
  インフラはこのコードから導出される（別のIaCファイルを書かない）。
- **Scope**: Blockの名前空間。`new Scope('my-app')` の下に各Blockを置く。
- **fullId**: `scope/id`（例 `my-app/todos`）。これが**AWSリソース名やローカル`.bb-data/`の
  ディレクトリ名の素**になる。だからID（第2引数）を変えるとリソースの同一性が変わる
  （→ rules-and-gotchas.md のデータ消失参照）。

## 自分の目で確かめる方法（read-onlyで実証）
解決先がconditionで変わることを、その場で確認できる:
```bash
# mock版が出る（condition指定なし）
node --input-type=module \
  -e "import('@aws-blocks/bb-distributed-table').then(m=>console.log(m.DistributedTable.toString().slice(0,200)))"

# 先頭に付けると cdk版 / aws版に切り替わる
NODE_OPTIONS=--conditions=cdk         node --input-type=module -e "..."
NODE_OPTIONS=--conditions=aws-runtime node --input-type=module -e "..."
```
さらに `NODE_OPTIONS=--conditions=cdk npx cdk synth` の出力 `cdk.out/*.template.json` を
`index.ts` と突き合わせると、`new DistributedTable(...)` 1行から DynamoDB::Table が生成される
のが見える。

## 見比べると理解が深まるファイル
1. `aws-blocks/index.ts`（書く側の1行） ↔ `node_modules/@aws-blocks/bb-distributed-table/dist/index.{mock,cdk,aws}.js`（3つの顔） ↔ 同パッケージの `package.json` `exports`（ルーティング表）
2. `cdk.json`（`-C cdk`） ↔ `@aws-blocks/core/dist/scripts/sandbox.js`（`NODE_OPTIONS=--conditions=cdk`） ↔ `@aws-blocks/core/dist/cdk/blocks-backend.js`（esbuild `aws-runtime`）
