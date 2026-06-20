---
name: aws-blocks
description: >-
  Guidance for building backends with AWS Blocks — the @aws-blocks/* TypeScript
  "infrastructure from code" framework where a single Block instantiation (e.g. new
  DistributedTable(scope, 'todos', {...})) resolves to a local in-memory/file mock during
  development, a CDK construct at deploy time, and an AWS SDK call in Lambda, all via Node.js
  conditional exports. Use this skill whenever the project contains an aws-blocks/ directory,
  imports from @aws-blocks/blocks or any @aws-blocks/* package, or the user mentions AWS Blocks,
  Building Blocks, KVStore, DistributedTable, DistributedDatabase, Database, FileBucket,
  AuthBasic/AuthCognito/AuthOIDC, Realtime, AsyncJob, CronJob, Agent, ApiNamespace, Scope, the
  IFC layer, BlocksContext, or runs npm run dev/sandbox/deploy in such a project — even if they
  do not name the framework explicitly. It routes to the SDK's bundled per-block docs and
  encodes the framework's mental model and critical footguns (Block-ID rename = permanent data
  loss, the --conditions=cdk flag, DSQL parity limits). Do NOT use this skill for plain AWS CDK,
  AWS Amplify, SST, or generic DynamoDB/Lambda/API Gateway work that does not involve @aws-blocks.
license: MIT
---

# AWS Blocks Implementation Guide (Steering Layer)

AWS Blocks is the `@aws-blocks/*` TypeScript "Infrastructure from Code" framework.
This skill is a **thin steering layer + router**. It is not an API reference.
**The canonical docs ship inside the SDK** (`node_modules/@aws-blocks/blocks/docs/`) and always
match the installed version. This skill's job is to (1) give you the correct mental model,
(2) route you to the bundled docs, and (3) prevent the critical footguns before they happen.

## The one-liner mental model

The **same single line** you write — `new DistributedTable(scope, 'todos', {...})` — resolves to a
**different implementation** per execution context, via Node.js conditional exports:

| Context                            | Resolved implementation                          | Behavior                           |
| ---------------------------------- | ------------------------------------------------ | ---------------------------------- |
| Local dev `npm run dev`            | mock (in-memory + JSON/PGlite under `.bb-data/`) | No AWS, offline                    |
| CDK synth `npm run deploy/sandbox` | CDK construct                                    | Defines resources such as DynamoDB |
| Lambda runtime (production)        | AWS SDK calls                                    | Hits the real services             |

One codebase. No rewrites. Details in [references/mental-model.md](references/mental-model.md).

## Top rules (always follow)

1. **Before using a Block, read its bundled doc.** Each page has the API, options, local behavior,
   production behavior, and best practices. Location:
   `node_modules/@aws-blocks/blocks/docs/<package>.md`
   (if you can't find it, locate it with `find . -path '*@aws-blocks/blocks/docs/index.md' -not -path '*/.git/*'`).
2. **Always do persistence and cloud abstractions through a Building Block.** Don't use local arrays,
   your own files, or a separate local DB (the mock plays that role, so a Block deploys to AWS as-is).
3. **The JSON-RPC transport is transparent.** Don't hand-assemble RPC payloads. Call the typed API
   directly via `import { api } from 'aws-blocks'`. Backend types propagate to the frontend
   automatically (there is no codegen step).

## Block selection routing (always in this order)

1. First read the **decision tree** → `node_modules/@aws-blocks/blocks/docs/index.md`
   (a catalog + keywords that pick the right Block from "what you want to do").
2. Then read the **per-Block doc** → `node_modules/@aws-blocks/blocks/docs/<package>.md`.
3. Cross-cutting core concepts (`Scope` / `ApiNamespace` / `withAuth` / `RawRoute` / CORS / JSON-RPC)
   → `node_modules/@aws-blocks/blocks/docs/core.md`.
4. The overall guide (architecture, common mistakes) → `node_modules/@aws-blocks/blocks/README.md`.

Main Blocks and their uses (always go to the docs above for details):

| What you want to do                                            | Block                                        | Bundled doc                        |
| -------------------------------------------------------------- | -------------------------------------------- | ---------------------------------- |
| Key-value (cache/flags)                                        | `KVStore`                                    | bb-kv-store.md                     |
| Structured data + indexes + queries (**the default for data**) | `DistributedTable`                           | bb-distributed-table.md            |
| Serverless SQL (basic Postgres-compatible)                     | `DistributedDatabase` (Aurora DSQL)          | bb-distributed-data.md             |
| Full Postgres (FK/RLS/triggers/large transactions)             | `Database` (Aurora Serverless v2)            | bb-data.md                         |
| Files/uploads                                                  | `FileBucket`                                 | bb-file-bucket.md                  |
| Auth (prototype/production/OIDC)                               | `AuthBasic` / `AuthCognito` / `AuthOIDC`     | bb-auth-\*.md                      |
| WebSocket pub/sub                                              | `Realtime`                                   | bb-realtime.md                     |
| Background jobs / scheduled runs                               | `AsyncJob` / `CronJob`                       | bb-async-job.md / bb-cron-job.md   |
| AI agents / RAG                                                | `Agent` / `KnowledgeBase`                    | bb-agent.md / bb-knowledge-base.md |
| Email / settings / observability                               | `EmailClient` / `AppSetting` / `Logger` etc. | bb-email-client.md and others      |

**Choosing a data Block**: the default is `DistributedTable`. Go to SQL only when you need JOINs across
multiple records, multi-dimensional filtering, transactions, or SQL flexibility. If you need SQL, prefer
`DistributedDatabase` (DSQL, zero idle cost) as a rule. Use `Database` (Aurora Serverless v2, with a
minimum 0.5 ACU idle cost or a cold start) only when you need FK/RLS/triggers, transactions over 3,000
rows, or integration with existing Postgres.

## Critical warnings (inline; details in rules-and-gotchas.md)

- ⚠️ **Renaming a Block ID (the 2nd constructor argument) = deleting and recreating the resource =
  permanent data loss for stateful Blocks.** Treat IDs as immutable after deploy.
- ⚠️ **Every API is public by default.** A gate only takes effect once you explicitly call
  `requireAuth()` / `requireRole()` inside the method. Forgetting it = an authorization hole.
- ⚠️ **DSQL (`DistributedDatabase`) has constraints: no DDL, no FK, no JSONB, and more.** The mock
  rejects these at dev time, but **OCC (optimistic concurrency) conflicts do not arise naturally**, so
  test them with `simulateConflict()` and finally verify on real infra with `npm run sandbox`.
- ⚠️ **Dropping `--conditions=cdk` leaks the mock into CDK synth.** Always use `npm run sandbox/deploy`
  (they set `NODE_OPTIONS=--conditions=cdk` automatically). Don't invoke a bare `cdk synth` directly.

Details, workarounds, and minimal code examples → [references/rules-and-gotchas.md](references/rules-and-gotchas.md)

## Development workflow (details in workflow-troubleshooting.md)

| Command                                       | What happens                                                                        |
| --------------------------------------------- | ----------------------------------------------------------------------------------- |
| `npm run dev`                                 | All Blocks start locally as mocks (persisted under `.bb-data/`). No AWS, hot reload |
| `npm run test:e2e`                            | e2e with the typed client. Auto-starts dev if it isn't running                      |
| `npm run sandbox` / `npm run sandbox:destroy` | Fast deploy to real AWS (Lambda hot-swap) / teardown                                |
| `npm run deploy` / `npm run destroy`          | Full production deploy (CloudFormation) / teardown                                  |

Fast iteration: start `npm run dev &` in the background and re-run `npm run test:e2e` (reusing the
server each time). **Don't fire curl/fetch directly at the API** (except when debugging connection
issues). Call the typed API directly. Details and a symptom→cause→fix table →
[references/workflow-troubleshooting.md](references/workflow-troubleshooting.md)

## The shape of the backend (IFC layer)

The backend is consolidated into a single file, `aws-blocks/index.ts` (= the IFC layer). There you
instantiate Blocks, define the API with `ApiNamespace`, and `export` it. The frontend (`src/`) calls it
type-safely via `import { api } from 'aws-blocks'`. The CDK definition lives in an optional
`aws-blocks/index.cdk.ts` (`BlocksStack.create({ backendCDKPath: './index.ts', ... })`), which re-reads
that same `index.ts` under the `cdk` condition to derive the infrastructure.

## Reference files (read as needed)

| File                                                                             | When to read                                                                                               |
| -------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| [references/mental-model.md](references/mental-model.md)                         | To understand the two layers of conditional exports, the switches, and why things break                    |
| [references/rules-and-gotchas.md](references/rules-and-gotchas.md)               | To avoid the data-loss / authorization / DSQL / conditions footguns (recommended read before implementing) |
| [references/workflow-troubleshooting.md](references/workflow-troubleshooting.md) | For commands, environment differences, the e2e loop, and resolving errors                                  |

And don't forget: **for the exact API of any individual Block, always consult the bundled
`node_modules/@aws-blocks/blocks/docs/<package>.md`.** This skill is a guide to that location; it
keeps no copy of the API (to avoid version mismatch).
