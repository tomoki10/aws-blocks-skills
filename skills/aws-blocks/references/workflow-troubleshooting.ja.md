---
lang: ja
source: workflow-troubleshooting.md
source_sha: b43dd21a5a404108479a594d33b61ea5d2081044
---

> 📖 これは [workflow-troubleshooting.md](workflow-troubleshooting.md) の日本語訳です。**正典は英語版**で、差異がある場合は英語が優先されます。
> このファイルは AI には読み込まれません（人間の読者・保守者向け）。

# ワークフロー・コマンド・トラブルシューティング

## コマンド早見
| コマンド | 何が起きるか | condition |
|---|---|---|
| `npm run dev` | 全Blockがmockでローカル起動。`http://localhost:3000`、ホットリロード、`.bb-data/`に永続化。AWS不要 | なし(default=mock) |
| `npm run test:e2e` | 型付きクライアントでe2e。dev未起動なら自動起動 | なし(default=mock) |
| `npm run sandbox` | 実AWSへ高速デプロイ（Lambdaホットスワップ）。各開発者ごとに分離。フロントはローカル提供 | `cdk`→synth, `aws-runtime`→bundle |
| `npm run sandbox:destroy` | サンドボックスのAWSリソースを撤去 | `cdk` |
| `npm run deploy` | 本番フルデプロイ（CloudFormation、Hosting含む） | `cdk`→synth, `aws-runtime`→bundle |
| `npm run destroy` | 本番リソースを撤去 | `cdk` |

> デプロイには AWS 認証情報と、初回のみ CDK bootstrap（`npx cdk bootstrap aws://ACCOUNT/REGION`）が必要。

## 3つの実行モードの違い
| | ローカル(dev) | サンドボックス(sandbox) | 本番(deploy) |
|---|---|---|---|
| Blockの実体 | mock（メモリ/ファイル/PGlite） | 実AWSサービス | 実AWSサービス |
| データの居場所 | `.bb-data/` | AWS（一時・開発者ごと） | AWS（永続） |
| 速度/コスト | 即時・無料 | 数秒・低コスト | CFn・本番構成 |
| 主な用途 | 反復開発・ロジック検証 | parity検証（DynamoDB/IAM/DSQLの実挙動） | ステージング/本番 |

**parity gap の原則**: mockは便利だが本物と完全一致ではない（特にDynamoDBの整合性/索引制約、
DSQLのOCC/分散挙動、IAM権限）。「ローカルで動く」を過信せず、微妙な挙動は `npm run sandbox` で確かめる。

## 高速反復ループ（推奨）
```bash
npm run dev &           # 背景でdevサーバ起動（mock）
npm run test:e2e        # 何度でも繰り返す（起動済みサーバを再利用）
```
- バックエンド(`aws-blocks/index.ts`) かフロント(`src/`) を編集 → `test:e2e` を回す。
- **APIへ curl/fetch を直接投げない**（接続トラブル調査時のみ例外）。型付きAPIを直接呼ぶ。
- フロントは `import { api } from 'aws-blocks'`。バックエンドの型がそのまま効く。

## 症状 → 原因 → 修正
| 症状 | 典型的な原因 | 修正 |
|---|---|---|
| ローカルでは通るのに本番/サンドボックスで失敗 | parity gap（DynamoDB整合性・索引制約・DSQLのOCC・IAM権限など mockが再現しない差） | `npm run sandbox` で実機検証。該当Blockの `docs/<package>.md` の「Local Development / Scaling」節を確認 |
| CDK synthで空/おかしいインフラ、`assertCdkConditionActive` 例外 | `--conditions=cdk` が無く mock が synth に混入 | 素の `cdk` を直接叩かず `npm run sandbox`/`deploy` を使う。直叩き時は `NODE_OPTIONS="--conditions=cdk"` |
| `DsqlValidationError`（FK/SERIAL/JSONB/TRUNCATE等） | DSQLが非対応の構文を使った | UUID採用・FK廃止・JSON列に変更など。`rules-and-gotchas.ja.md` の§3を参照 |
| `TransactionRowLimitExceededException` | 1トランザクションで3,000行超を変異 | バッチ分割。または `Database`(フルPostgres)を検討 |
| DDLがアプリ実行時に拒否される | DSQLはDDLをマイグレーションのみ許可 | スキーマ変更はマイグレーションファイルへ。1ファイル=1DDL |
| 認証したのに誰でもAPIを呼べる | メソッド内で `requireAuth()`/`requireRole()` 未呼び出し | 各保護メソッドでゲートを明示。`docs/core.md`/`docs/bb-auth-*.md` |
| フロントで型が出ない/古い | `client.js` 未再生成 | `npm run dev` を起動（編集監視で自動再生成）。`client.js` は手で編集しない |
| デプロイで認証情報エラー | AWS未設定 or CDK未bootstrap | `aws sts get-caller-identity` 確認、`npx cdk bootstrap` 実行 |
| ローカルのデータをリセットしたい | `.bb-data/` にmockデータが残存 | 該当 `.bb-data/<fullId>/` を削除（本番には無影響） |

## デプロイ時のモード分岐（参考）
`aws-blocks/index.cdk.ts` は `app.node.tryGetContext('sandboxMode')` で分岐し、sandbox時は
削除保護を外し `BLOCKS_SANDBOX=true` を設定、本番時のみ `Hosting`(S3+CloudFront) を足す、といった
構成になっていることが多い。カスタムCDKリソースを足すならこのファイルに追記する
（`BlocksStack.create(...)` の戻り値 `blocksStack` / `blocksStack.handler` を使う）。
