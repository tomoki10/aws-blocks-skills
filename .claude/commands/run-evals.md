---
description: Run aws-blocks A/B benchmark (with_skill vs without_skill) and open the results viewer
argument-hint: "[--eval <id>] [--runs <n>] [--workspace <path>]"
allowed-tools: Bash(cp -r*), Bash(ln -s*), Bash(mkdir -p*), Bash(python3*), Bash(ls*), Bash(cat*), Bash(git hash-object*), Read, Edit, Write, Agent
---

Run an A/B benchmark for the `aws-blocks` skill. Each eval prompt is executed in a disposable
sandbox — once with the skill loaded (with_skill) and once without (without_skill). The grader
scores each run against the expectations defined in `evals.json`, then the aggregator computes
pass-rate delta (with − without) to show whether the skill actually helps.

## Arguments

- `--eval <id>`: run only eval with this id (0, 1, or 2). Default: all three.
- `--runs <n>`: number of runs per configuration (default: 1 for smoke test, 3 for full).
- `--workspace <path>`: where to write results (default: `/tmp/aws-blocks-benchmark/iteration-1`).

## Dependencies (must be installed)

skill-creator plugin:
```
~/.claude/plugins/marketplaces/anthropic-agent-skills/skills/skill-creator/
```

If missing, install via: `claude /find-skills skill-creator`

## Step 1 — Resolve arguments

Parse `$*`:
- `EVAL_IDS`: list of eval ids to run (default `[0, 1, 2]`).
- `RUNS`: number of runs per config (default `1`).
- `WORKSPACE`: result root (default `/tmp/aws-blocks-benchmark/iteration-1`).

```sh
mkdir -p "$WORKSPACE"
```

## Step 2 — Read eval definitions

Read `skills/aws-blocks/evals/evals.json`. For each eval in `EVAL_IDS`, extract:
- `id`, `name`, `prompt`, `fixture`, `expectations`

## Step 3 — For each eval × configuration × run

Repeat for each `eval_id` in `EVAL_IDS`, each `config` in `[with_skill, without_skill]`,
each `run_index` from 1 to `RUNS`:

### 3a. Create the sandbox

```sh
SANDBOX=/tmp/aws-blocks-sandbox-eval${eval_id}-${config}-run${run_index}
cp -r /Users/sato.tomoki/Documents/aws_work/aws_blocks_work/my-app "$SANDBOX"
# Symlink node_modules from the real project to keep the copy lightweight
rm -rf "$SANDBOX/node_modules"
ln -s /Users/sato.tomoki/Documents/aws_work/aws_blocks_work/my-app/node_modules "$SANDBOX/node_modules"
```

### 3b. Apply the fixture

Overwrite `aws-blocks/index.ts` with the fixture for this eval:

```sh
FIXTURE_DIR="$(git rev-parse --show-toplevel)/skills/aws-blocks/evals/fixtures/<fixture_name>"
cp "$FIXTURE_DIR/index.ts" "$SANDBOX/aws-blocks/index.ts"
```

Where `<fixture_name>` is the `fixture` field from `evals.json` (`blank-ifc` or `todos-seeded`).

### 3c. Create the run directory

```sh
RUN_DIR="$WORKSPACE/eval-${eval_id}/${config}/run-${run_index}"
mkdir -p "$RUN_DIR/outputs"
```

Write `eval_metadata.json` in `$WORKSPACE/eval-${eval_id}/`:
```json
{"eval_id": <id>, "eval_name": "<name>"}
```

### 3d. Execute — spawn an executor Agent

**with_skill prompt template:**
```
You are implementing a feature for an AWS Blocks project.

Project sandbox: <SANDBOX>
Task: <eval.prompt>

IMPORTANT: Before implementing, read the aws-blocks skill documentation:
- <SKILL_ROOT>/SKILL.md
- <SKILL_ROOT>/references/ (all .md files)

Then implement the task by modifying <SANDBOX>/aws-blocks/index.ts.
Save your implementation notes to <RUN_DIR>/outputs/implementation.md.
Write a transcript of your reasoning and steps to <RUN_DIR>/transcript.md.
```

**without_skill prompt template:**
```
You are implementing a feature for an AWS Blocks project.

Project sandbox: <SANDBOX>
Task: <eval.prompt>

Implement the task by modifying <SANDBOX>/aws-blocks/index.ts.
Save your implementation notes to <RUN_DIR>/outputs/implementation.md.
Write a transcript of your reasoning and steps to <RUN_DIR>/transcript.md.
```

Where `<SKILL_ROOT>` = `$(git rev-parse --show-toplevel)/skills/aws-blocks`.

Record start/end timestamps and write `<RUN_DIR>/timing.json`:
```json
{"started_at": "<ISO8601>", "finished_at": "<ISO8601>", "duration_seconds": <n>}
```

### 3e. Grade — invoke the grader agent

Spawn the grader by reading the grader runbook:

```
~/.claude/plugins/marketplaces/anthropic-agent-skills/skills/skill-creator/agents/grader.md
```

Pass:
- `expectations`: the expectations array from `evals.json` for this eval
- `transcript_path`: `<RUN_DIR>/transcript.md`
- `outputs_dir`: `<RUN_DIR>/outputs/`

The grader writes `<RUN_DIR>/grading.json`.

### 3f. Clean up the sandbox

```sh
rm -rf "$SANDBOX"
```

## Step 4 — Aggregate

```sh
SKILL_CREATOR=~/.claude/plugins/marketplaces/anthropic-agent-skills/skills/skill-creator
python3 "$SKILL_CREATOR/scripts/aggregate_benchmark.py" "$WORKSPACE"
```

This writes `$WORKSPACE/benchmark.json` and `$WORKSPACE/benchmark.md`.

## Step 5 — Open the viewer

```sh
python3 "$SKILL_CREATOR/eval-viewer/generate_review.py" "$WORKSPACE" --skill-name aws-blocks
```

This starts a local HTTP server and opens the browser.

## Step 6 — Check i18n consistency (optional)

```sh
bash scripts/check-i18n.sh
```

Should exit 0.

## Step 7 — Summarize for the user

Report:
- Which evals ran, how many runs per config
- Pass rates: with_skill vs without_skill per eval
- Delta (positive = skill helped)
- Path to `$WORKSPACE/benchmark.md` for the full table
- Any grading.json that showed unexpected failures
