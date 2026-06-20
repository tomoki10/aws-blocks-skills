# Workflow, commands, and troubleshooting

## Command cheat sheet
| Command | What happens | condition |
|---|---|---|
| `npm run dev` | All Blocks start locally as mocks. `http://localhost:3000`, hot reload, persisted to `.bb-data/`. No AWS | none (default=mock) |
| `npm run test:e2e` | e2e with the typed client. Auto-starts dev if it isn't running | none (default=mock) |
| `npm run sandbox` | Fast deploy to real AWS (Lambda hot-swap). Isolated per developer. Frontend served locally | `cdk`→synth, `aws-runtime`→bundle |
| `npm run sandbox:destroy` | Tear down the sandbox's AWS resources | `cdk` |
| `npm run deploy` | Full production deploy (CloudFormation, including Hosting) | `cdk`→synth, `aws-runtime`→bundle |
| `npm run destroy` | Tear down production resources | `cdk` |

> Deploying requires AWS credentials and, on the first run only, a CDK bootstrap
> (`npx cdk bootstrap aws://ACCOUNT/REGION`).

## Differences between the three execution modes
| | Local (dev) | Sandbox (sandbox) | Production (deploy) |
|---|---|---|---|
| Block's real form | mock (memory/files/PGlite) | real AWS services | real AWS services |
| Where the data lives | `.bb-data/` | AWS (ephemeral, per developer) | AWS (persistent) |
| Speed/cost | instant, free | seconds, low cost | CFn, production config |
| Main use | iterative dev, logic checks | parity verification (real DynamoDB/IAM/DSQL behavior) | staging/production |

**The parity-gap principle**: the mock is convenient but not a perfect match for the real thing
(especially DynamoDB consistency/index constraints, DSQL OCC/distributed behavior, and IAM permissions).
Don't over-trust "it works locally" — check subtle behavior with `npm run sandbox`.

## The fast iteration loop (recommended)
```bash
npm run dev &           # start the dev server (mock) in the background
npm run test:e2e        # repeat as many times as you like (reuses the running server)
```
- Edit the backend (`aws-blocks/index.ts`) or the frontend (`src/`) → run `test:e2e`.
- **Don't fire curl/fetch directly at the API** (except when investigating connection issues). Call the
  typed API directly.
- The frontend uses `import { api } from 'aws-blocks'`. The backend types apply directly.

## Symptom → cause → fix
| Symptom | Typical cause | Fix |
|---|---|---|
| Passes locally but fails in production/sandbox | parity gap (DynamoDB consistency, index constraints, DSQL OCC, IAM permissions, and other differences the mock doesn't reproduce) | Verify on real infra with `npm run sandbox`. Check the "Local Development / Scaling" section of that Block's `docs/<package>.md` |
| Empty/wrong infra on CDK synth, `assertCdkConditionActive` exception | `--conditions=cdk` is missing and the mock leaked into synth | Don't invoke bare `cdk`; use `npm run sandbox`/`deploy`. When invoking directly, add `NODE_OPTIONS="--conditions=cdk"` |
| `DsqlValidationError` (FK/SERIAL/JSONB/TRUNCATE etc.) | Used syntax DSQL doesn't support | Adopt UUIDs, drop FKs, switch to a JSON column, etc. See §3 of `rules-and-gotchas.md` |
| `TransactionRowLimitExceededException` | Mutated more than 3,000 rows in one transaction | Split into batches. Or consider `Database` (full Postgres) |
| DDL rejected at application runtime | DSQL only allows DDL in migrations | Move schema changes into migration files. 1 file = 1 DDL |
| Authenticated, yet anyone can call the API | `requireAuth()`/`requireRole()` not called inside the method | Make the gate explicit in each protected method. `docs/core.md`/`docs/bb-auth-*.md` |
| Frontend types missing/stale | `client.js` not regenerated | Start `npm run dev` (auto-regenerates on edit-watch). Don't edit `client.js` by hand |
| Credentials error on deploy | AWS not configured or CDK not bootstrapped | Check `aws sts get-caller-identity`, run `npx cdk bootstrap` |
| Want to reset local data | mock data left under `.bb-data/` | Delete the relevant `.bb-data/<fullId>/` (no effect on production) |

## Mode branching at deploy time (for reference)
`aws-blocks/index.cdk.ts` often branches on `app.node.tryGetContext('sandboxMode')`: in sandbox it
disables deletion protection and sets `BLOCKS_SANDBOX=true`, and only in production it adds `Hosting`
(S3+CloudFront). If you add custom CDK resources, append them to this file (use the return value of
`BlocksStack.create(...)` — `blocksStack` / `blocksStack.handler`).
