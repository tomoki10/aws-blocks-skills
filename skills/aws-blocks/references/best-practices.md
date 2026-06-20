# Best practices (router + cross-cutting additions)

The official AWS Blocks best practices **already ship inside the SDK** and match the installed version, so
this skill does **not** copy them (copying risks version drift — and it already happened: the public web
page tells you to partition one `KVStore` by key prefix, while the version-matched
`docs/bb-kv-store.md` says *"Store one logical entity per KVStore instance"* — **when they differ, follow
the bundled doc**).

This file therefore (1) routes each best-practice topic to its canonical bundled location, and (2) keeps
only the few cross-cutting practices the bundled docs don't already state.

## Where the canonical best practices live (read these first)

| Topic | Canonical bundled location |
| --- | --- |
| Headline best practices (export the API, validate with schemas, don't block the request → `AsyncJob`, guard races with conditional writes, test locally first) | `node_modules/@aws-blocks/blocks/README.md` → **## Best practices** |
| Common mistakes (ungated endpoints, forgetting to export, `Database` overuse, curling REST paths) | `README.md` → **## Common mistakes** |
| Error handling (named errors, `isBlocksError`, the real `ApiError` API, per-block error-name constants like `KVStoreErrors.*`) | `docs/core.md` → **ApiError / isBlocksError** + each `docs/<block>.md` → **Error Handling** |
| Auth — every method public by default, `requireAuth` / `requireRole`, per-user data scoping | `README.md` → **Adding auth and data** (Security callout) + `docs/core.md`; also [rules-and-gotchas.md](rules-and-gotchas.md) §2 |
| Auth block selection (`AuthBasic` / `AuthCognito` / `AuthOIDC`) | `docs/index.md` + `README.md` Building Blocks table |
| Data block selection (`DistributedTable` vs SQL) | `docs/index.md` → **Choosing a data block** |
| Per-block usage (key/index design, conditional writes, payload/item-size limits, scan vs query) | each `docs/<block>.md` → **## Best Practices** + **## Scaling & Cost** |
| Local dev vs sandbox vs deploy, `.bb-data` reset, parity gap | `README.md` → **Local development and deploying** + [workflow-troubleshooting.md](workflow-troubleshooting.md) |
| e2e testing via the typed import | `README.md` → **## Testing** + [workflow-troubleshooting.md](workflow-troubleshooting.md) |

## Cross-cutting practices the bundled docs don't state

Keep these here because no bundled doc covers them:

- **Project structure.** Use a **single `Scope` per application** (multiple scopes = separate resource
  namespaces, complexity without benefit). Keep `aws-blocks/index.ts` **thin** — Block instantiation + API
  definition only — and move business logic into separate modules (e.g. `aws-blocks/orders.ts`).
  **Co-locate** related domains (orders, users, notifications) in the same IFC-layer file until it grows
  unwieldy.
- **Unit-test in isolation.** The thin-IFC structure pays off here: extract logic into **pure functions
  that take Block instances as parameters**, then unit-test them with mock Blocks — no framework needed.
  (For integration/e2e against mocks or sandbox, use the bundled **README ## Testing** loop +
  [workflow-troubleshooting.md](workflow-troubleshooting.md).)
  ```ts
  // orders.ts — extracted, testable
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
- **Multiple environments.** AWS Blocks deploys the *same* code to any account (resources are derived from
  code, not env config), so use **separate AWS accounts for dev / staging / prod**. Put environment-specific
  settings — custom domain, VPC, WAF, `CORS_ALLOWED_ORIGINS` — in `aws-blocks/index.cdk.ts`, not in runtime
  code. (CORS env-var example → `docs/core.md` **CORS Configuration**; sandbox/prod mode branching →
  [workflow-troubleshooting.md](workflow-troubleshooting.md).)
- **Working with AI coding agents.** Give agents good context: **descriptive Block IDs**
  (`new KVStore(scope, 'user-sessions', {})` over `'s1'` — but remember IDs are immutable after deploy,
  [rules-and-gotchas.md](rules-and-gotchas.md) §1) and **JSDoc on API methods** so agents infer intent when
  generating frontend code. Installing the Block packages also makes their bundled docs/types available as
  agent context (this skill's top rule #1).
