---
lang: ja
source: best-practices.md
source_sha: 80175b3096fadcec86c21b23dffead3df20ca8d4
---

> 📖 これは [best-practices.md](best-practices.md) の日本語訳です。**正典は英語版**で、差異がある場合は英語が優先されます。
> このファイルは AI には読み込まれません（人間の読者・保守者向け）。

# ベストプラクティス（ルーター + 横断的な追加分）

公式の AWS Blocks ベストプラクティスは**SDKに同梱されており**インストール済みバージョンと一致するため、
このSkillはそれを**複製しない**（複製はバージョン乖離を招く — 実際に起きている: 公開Webページは1つの
`KVStore` をキープレフィックスで分割せよと言うが、バージョン一致の `docs/bb-kv-store.md` は
*「Store one logical entity per KVStore instance（KVStoreインスタンス1つに付き論理エンティティ1つ）」*と
言う。**食い違う場合は同梱docに従う**）。

よってこのファイルは、(1) 各ベストプラクティスのトピックを正典の同梱ロケーションへルーティングし、
(2) 同梱docがまだ述べていない横断的な実践だけを保持する。

## 正典のベストプラクティスの所在（まずこれを読む）

| トピック | 正典の同梱ロケーション |
| --- | --- |
| 主要なベストプラクティス（APIをexport、schemaで検証、リクエストを塞がず `AsyncJob` へ、条件付き書き込みで競合を防ぐ、まずローカルでテスト） | `node_modules/@aws-blocks/blocks/README.md` → **## Best practices** |
| よくある間違い（ゲート無しエンドポイント、export忘れ、`Database` の使い過ぎ、RESTパスへのcurl） | `README.md` → **## Common mistakes** |
| エラー処理（名前付きエラー、`isBlocksError`、実際の `ApiError` API、`KVStoreErrors.*` 等のBlock別エラー名定数） | `docs/core.md` → **ApiError / isBlocksError** + 各 `docs/<block>.md` → **Error Handling** |
| 認証 — 全メソッド既定で公開、`requireAuth` / `requireRole`、ユーザー単位のデータ分離 | `README.md` → **Adding auth and data**（Securityコールアウト）+ `docs/core.md`、加えて [rules-and-gotchas.ja.md](rules-and-gotchas.ja.md) §2 |
| 認証Block選定（`AuthBasic` / `AuthCognito` / `AuthOIDC`） | `docs/index.md` + `README.md` の Building Blocks 表 |
| データBlock選定（`DistributedTable` vs SQL） | `docs/index.md` → **Choosing a data block** |
| Block別の使い方（キー/索引設計、条件付き書き込み、ペイロード/アイテムサイズ上限、scan vs query） | 各 `docs/<block>.md` → **## Best Practices** + **## Scaling & Cost** |
| ローカル開発 vs sandbox vs deploy、`.bb-data` リセット、parity gap | `README.md` → **Local development and deploying** + [workflow-troubleshooting.ja.md](workflow-troubleshooting.ja.md) |
| 型付きimport経由のe2eテスト | `README.md` → **## Testing** + [workflow-troubleshooting.ja.md](workflow-troubleshooting.ja.md) |

## 同梱docが述べていない横断的な実践

同梱docがカバーしないため、ここに残す:

- **プロジェクト構成。** アプリ1つに付き **`Scope` は1つ**（複数Scope = リソース名前空間の分割、利点なく
  複雑さだけ増す）。`aws-blocks/index.ts` は **薄く** 保ち（Blockインスタンス化 + API定義だけ）、業務
  ロジックは別モジュール（例 `aws-blocks/orders.ts`）へ移す。関連ドメイン（orders・users・notifications）は
  ファイルが肥大化するまで同じIFC層ファイルに **co-locate** する。
- **単独で単体テストする。** 薄いIFC構造はここで効く: ロジックを **Blockインスタンスを引数に取る純粋関数**
  へ抽出し、mock Blockで単体テストする — フレームワーク不要。（mock/sandboxに対する結合・e2eは、同梱の
  **README ## Testing** ループ + [workflow-troubleshooting.ja.md](workflow-troubleshooting.ja.md) を使う。）
  ```ts
  // orders.ts — 抽出済み・テスト可能
  export async function createOrder(store, userId, input) {
    if (!input.title) throw new Error('Title required');
    const order = { id: crypto.randomUUID(), ...input, userId };
    await store.put({ ...order });
    return order;
  }
  // orders.test.ts
  const mockStore = { put: vi.fn(), query: vi.fn() };
  expect((await createOrder(mockStore, 'user-1', { title: 'T' })).title).toBe('T');
  ```
- **複数環境。** AWS Blocks は*同じ*コードをどのアカウントにもデプロイする（リソースは環境設定でなく
  コードから導出される）ので、**dev / staging / prod でAWSアカウントを分ける**。環境固有の設定 —
  カスタムドメイン・VPC・WAF・`CORS_ALLOWED_ORIGINS` — は実行時コードでなく `aws-blocks/index.cdk.ts` に
  置く。（CORS環境変数の例 → `docs/core.md` の **CORS Configuration**、sandbox/prod のモード分岐 →
  [workflow-troubleshooting.ja.md](workflow-troubleshooting.ja.md)。）
- **AIコーディングエージェントとの協働。** エージェントに良いコンテキストを与える: **記述的なBlock ID**
  （`'s1'` より `new KVStore(scope, 'user-sessions', {})` — ただしIDはデプロイ後不変、
  [rules-and-gotchas.ja.md](rules-and-gotchas.ja.md) §1）と、フロント生成時の意図推定に使われる
  **APIメソッドのJSDoc**。Blockパッケージを導入すれば同梱doc/型もエージェントのコンテキストになる
  （本Skillの最重要ルール#1）。
