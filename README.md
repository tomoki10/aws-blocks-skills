# aws-blocks-skills

A [Skill](https://docs.claude.com/en/docs/claude-code/skills) that helps coding
agents build **AWS Blocks** backends correctly and fast — giving them the right mental model, routing
them to the framework's bundled docs, and steering them clear of the footguns that cause data loss and
broken deploys.

日本語版: [README.ja.md](README.ja.md)

## What is AWS Blocks?

[AWS Blocks](https://docs.aws.amazon.com/blocks/latest/devguide/what-is-blocks.html) is "a backend
toolkit for building full-stack applications on AWS." Each Block (`KVStore`, `DistributedTable`,
`FileBucket`, `AuthCognito`, `Realtime`, `Agent`, …) is a self-contained backend capability that bundles
application code, a local dev setup, and the AWS infrastructure to run it. Combine the ones you need and
AWS Blocks defines the infrastructure for you, following AWS best practices.

The defining idea is **one codebase, three resolutions** via Node.js conditional exports: the same line —
e.g. `new DistributedTable(scope, 'todos', {...})` — runs as a local in-memory/file mock in development,
becomes a CDK construct (real DynamoDB, etc.) at deploy, and calls the AWS SDK in Lambda. "Your entire
application runs locally without an AWS account … deploy the same code to AWS without changing anything."

## What this skill does

The framework already ships its canonical docs inside the npm package. This skill is a **thin steering
layer + router** on top of them — intentionally *not* an API reference, so it can never drift from your
installed version. It:

- **Gives the correct mental model** — why the same code resolves three ways, what the IFC layer /
  `Scope` / `fullId` are, and why that matters.
- **Routes to the bundled docs** — the canonical per-Block API lives in
  `node_modules/@aws-blocks/blocks/docs/<package>.md` and always matches your installed version; the
  skill points there instead of copying it.
- **Prevents the critical footguns** before they happen:
  - ⚠️ Renaming a Block ID = recreating the resource = **permanent data loss** for stateful Blocks.
  - ⚠️ APIs are **public by default** — auth gates apply only when you call `requireAuth()` / `requireRole()`.
  - ⚠️ DSQL (`DistributedDatabase`) parity limits, and why concurrency must be verified on real infra.
  - ⚠️ Dropping `--conditions=cdk` leaks the mock into CDK synth.
- **Picks the right Block** — a routing table from "what you want to do" to the Block and its doc
  (e.g. structured data → `DistributedTable`; serverless SQL → `DistributedDatabase`).

The result: an agent that builds on AWS Blocks correctly on the first attempt and reaches for the bundled
docs for exact APIs.

## When it activates

Claude triggers this skill automatically when a project uses AWS Blocks — an `aws-blocks/` directory,
imports from `@aws-blocks/*`, or mentions of Blocks such as `DistributedTable`, `ApiNamespace`, or
`npm run dev/sandbox/deploy`. See the `description` in [`skills/aws-blocks/SKILL.md`](skills/aws-blocks/SKILL.md)
for the full trigger list.

## Skills

| Skill | What it helps you do |
|---|---|
| [`aws-blocks`](skills/aws-blocks/SKILL.md) | Build backends with the `@aws-blocks/*` framework: pick the right Block, follow the local → sandbox → production workflow, and avoid the data-loss / auth / DSQL / `--conditions` footguns. |

## Repository layout

```
skills/
  aws-blocks/
    SKILL.md            # the skill (steering layer + router)
    references/         # mental-model, rules-and-gotchas, workflow-troubleshooting, best-practices
    evals/evals.json    # trigger/behavior eval cases
scripts/
  check-i18n.sh         # English -> Japanese translation drift checker
  check-upstream-docs.py  # upstream AWS docs drift checker
  upstream/             # manifest.json + snapshots/ (last-reviewed upstream content)
.github/workflows/check-upstream-docs.yml  # weekly upstream drift check
.claude/commands/refresh-best-practices.md # AI-assisted reflection runbook
```

## Documentation languages

Skills ship in **English** (the canonical version the AI loads) with a **Japanese companion** (`*.ja.md`)
for comfortable reading by Japanese speakers. English is the source of truth: each `*.ja.md` records the
`git hash-object` of its English source in frontmatter, so `scripts/check-i18n.sh` flags any translation
that has drifted out of date.

## Keeping content fresh

Two drift checkers keep this skill in sync, both built on the same "record a baseline hash, flag when it
changes" idea:

1. **Translation drift** — `scripts/check-i18n.sh` compares each `*.ja.md`'s recorded `source_sha`
   against the current `git hash-object` of its English source. Exit 0 = all in sync.
2. **Upstream docs drift** — `scripts/check-upstream-docs.py` tracks the upstream AWS docs that some
   skill content is derived from (currently the
   [Best practices page](https://docs.aws.amazon.com/blocks/latest/devguide/best-practices.html)). It
   re-fetches each page, normalizes the article body, and compares its sha256 against the baseline in
   `scripts/upstream/manifest.json`. A stored snapshot under `scripts/upstream/snapshots/` lets it show a
   **diff** of what changed. A weekly GitHub Actions workflow
   (`.github/workflows/check-upstream-docs.yml`) runs it and opens an `upstream-drift` issue when it
   changes.

Because `best-practices.md` deliberately **routes** to the SDK-bundled docs rather than copying the web
page (the bundled docs win on conflict), reflecting an upstream change is a judgement task, not a copy.
When drift is detected, run **`/refresh-best-practices`** in Claude Code: it reads the diff, applies only
the genuinely-new cross-cutting guidance, re-baselines the snapshot
(`python3 scripts/check-upstream-docs.py --update`), and fixes any translation drift it caused.
