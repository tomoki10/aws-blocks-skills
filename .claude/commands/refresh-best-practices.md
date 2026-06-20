---
description: Review upstream AWS Blocks best-practices drift and reflect it into the skill
argument-hint: "[source-id, default: best-practices]"
allowed-tools: Bash(python3 scripts/check-upstream-docs.py*), Bash(bash scripts/check-i18n.sh), Bash(git hash-object*), Read, Edit, Grep, Glob
---

You are reflecting an upstream AWS documentation change into this skill repository. The upstream
source-id is `$1` (default `best-practices` if empty). Work carefully — this is a judgement task,
not a mechanical copy.

## Critical design constraint (do not violate)

`skills/aws-blocks/references/best-practices.md` **intentionally does not copy** the upstream page.
It is a **router + cross-cutting additions**: it points each topic to its canonical location in the
SDK-bundled docs (`node_modules/@aws-blocks/blocks/docs/*` and that package's `README.md`) and keeps
inline only the few practices the bundled docs don't state. When the public page and the
version-matched bundled doc disagree, **the bundled doc wins**. Preserve this — never turn the file
into a copy of the web page.

## Steps

1. **See what changed.** Run:
   `python3 scripts/check-upstream-docs.py $1`
   - Exit 0 / `OK` → nothing to do; tell the user there is no drift and stop.
   - Exit 2 / `ERROR` → fetch failed or the page structure changed; report it (the extractor in
     `scripts/check-upstream-docs.py` may need updating) and stop.
   - Exit 1 / `CHANGED` → read the printed unified diff; that is the upstream change to reflect.

2. **Classify each diff hunk** before editing anything:
   - **Already covered by a bundled doc** (error handling, auth, per-block usage, block selection,
     local-dev/testing, common mistakes)? → do NOT inline it. At most, check the routing table in
     `best-practices.md` still points to the right bundled location; adjust the pointer if a section
     was renamed.
   - **Conflicts with a bundled doc**? → keep following the bundled doc; if useful, note the
     divergence as a caution (as the existing KVStore key-prefix note does).
   - **Genuinely new cross-cutting guidance** not in any bundled doc (project structure, isolated
     unit testing, multi-environment/accounts, AI-agent collaboration)? → this is what may warrant an
     edit.

3. **Apply minimal edits** for the "genuinely new" items only, to:
   - `skills/aws-blocks/references/best-practices.md` (canonical English), and
   - the `## Best practices` section of `skills/aws-blocks/SKILL.md` if the headline summary changed.
   - Touch `references/rules-and-gotchas.md` only if the change is a new footgun.
   Keep the voice and structure of the existing files. Do not add API specifics that could drift —
   route to the bundled docs instead.

4. **Re-baseline the upstream snapshot:**
   `python3 scripts/check-upstream-docs.py --update $1`
   Then confirm a clean run: `python3 scripts/check-upstream-docs.py $1` → `OK`.

5. **Fix translation drift.** Run `bash scripts/check-i18n.sh`. For every file it reports `STALE`
   (e.g. `best-practices.ja.md`, `SKILL.ja.md`), update the Japanese translation to match the new
   English, then set its frontmatter `source_sha` to the new English hash from
   `git hash-object <english-file>`. Re-run `bash scripts/check-i18n.sh` until everything is `OK`.

6. **Summarize for review.** Report: which diff hunks you reflected vs. deliberately skipped (and
   why — e.g. "already in bundled core.md"), the files you edited, and confirmation that both
   `check-upstream-docs.py` and `check-i18n.sh` are green. Leave committing to the user.
