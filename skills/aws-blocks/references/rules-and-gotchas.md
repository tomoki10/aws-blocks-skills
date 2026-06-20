# Rules to follow and critical footguns

A roundup of AWS Blocks-specific points that bite if you don't know them. Always read the per-Block
spec in the bundled `node_modules/@aws-blocks/blocks/docs/<package>.md` alongside this.

## 1. Renaming a Block ID = permanent data loss (most important)
A Block's 2nd argument (the ID) becomes the `fullId` `scope/id`, which is the basis for the AWS resource
name. **Changing the ID deletes the old resource and creates a new one on the next deploy** → for
stateful Blocks like `KVStore` / `DistributedTable` / `Database` / `DistributedDatabase` / `FileBucket`,
**the stored data is lost forever**.
```ts
// Already deployed. Changing this from 'todos' to 'todoItems' recreates the DynamoDB table and wipes everything.
const todos = new DistributedTable(scope, 'todos', { /* ... */ });
```
**Avoid**: treat post-deploy IDs as immutable. Changing the display name or variable name is fine, but
don't change the 2nd-argument string. If you truly must change it, design a data migration
(export → new Block → import).

## 2. Auth is public by default; gates are manual
Every method on `ApiNamespace` is **callable by anyone by default**. Authorization only takes effect once
you **explicitly call** `requireAuth()` / `requireRole()` inside the method. Forgetting it = an
authorization hole.
```ts
export const api = new ApiNamespace(scope, 'api', (context) => ({
  async listMyTodos() {
    const user = await auth.getCurrentUser(context); // or auth.requireAuth(context)
    // scope by user.userId
  },
  async adminPurge() {
    await auth.requireRole(context, 'admin'); // without this, anyone could run it
  },
}));
```
For the exact method names and gate functions, see `docs/core.md` and `docs/bb-auth-*.md`.

## 3. DSQL (`DistributedDatabase`) parity limits
The local mock is **PGlite (a real Postgres compiled to WASM) + a DSQL validation layer**. PGlite is full
Postgres, so a validation layer **actively rejects** DSQL's constraints to keep dev close to production.

Errors at dev time (= constraints the mock reproduces):
- Foreign keys (`FOREIGN KEY`/`REFERENCES`), `SERIAL`/`SEQUENCE`, triggers, views, PL/pgSQL,
  `TRUNCATE`, `LISTEN/NOTIFY`, extensions, `JSONB` columns, RLS, temporary tables, `COLLATE`, etc. are
  **unsupported**.
- Transactions: no mixing DDL and DML, at most 1 DDL per transaction, and a **3,000-row mutation limit
  per transaction**.
- DDL (CREATE/ALTER/DROP) is **not allowed at application runtime**. It runs only in migration files
  (reproducing the IAM split where the production app Lambda has only `dsql:DbConnect` while the
  migration Lambda has `dsql:DbConnectAdmin`).

**What the mock cannot reproduce (be careful)**:
- **OCC (optimistic concurrency control) conflicts do not arise naturally** (PGlite is single-connection).
  To test a `40001` serialization failure, use `simulateConflict()`. You can confirm the retry logic of
  `transactionWithRetry` (`retryOnConflict`), but real conflict detection only happens on real infra.
- The visibility timing of ASYNC indexes, distributed-commit latency, and performance characteristics.

**Conclusion**: schema/syntax-level checks can be validated locally well enough. **Verify the real
behavior of concurrency and distribution on real infra with `npm run sandbox`.** For choosing between
SQL options (DSQL vs. full Postgres `Database`), follow "Choosing a data block" in `docs/index.md`.

## 4. Dropping `--conditions=cdk` leaks the mock in
During CDK synth, if the `cdk` condition is absent, Blocks are **synthed as their mock implementation**,
producing unintended (or empty) infrastructure. The framework detects this with
`assertCdkConditionActive()` and throws.
- **Always use `npm run sandbox` / `npm run deploy`** (they set `NODE_OPTIONS=--conditions=cdk`
  automatically).
- If you must invoke a bare `npx cdk synth/deploy`, add `NODE_OPTIONS="--conditions=cdk"`.
- The Lambda bundle separately gets `--conditions aws-runtime` from esbuild (don't override the built-in
  bundle config).

## 5. Don't use "plain local means" for persistence
If you use local arrays, your own files via `fs`, or a separate local DB, they won't connect to AWS at
deploy time. **Always persist through a Block** (the mock handles local behavior, so the same code
deploys as-is). Even for cache-like ephemeral memory, use `KVStore` if the state is shared.

## 6. JSON-RPC is transparent; types propagate to the frontend
Make API calls through the typed client directly. Don't build RPC URLs, hand-assemble payloads, or call
`fetch` directly. If you change a backend method signature, the frontend immediately fails to compile
(the strength of having no codegen step). Only use curl exceptionally when you want to check connectivity
while debugging.

## 7. Other common snags
- **`.bb-data/` is the real data of the local mock.** Deleting it clears your locally saved contents, but
  it is unrelated to production.
- **`Database` (Aurora Serverless v2) has idle cost / cold start** (minimum 0.5 ACU). If simple
  Postgres-compatibility is enough, prefer `DistributedDatabase` (DSQL, zero idle).
- **Importing existing resources** uses the `fromExisting()` family (e.g. existing Postgres, existing
  tables). See each doc for details.
