#!/usr/bin/env bash
# check-i18n.sh — detect drift between English canonical docs and their *.ja.md translations.
#
# Convention: each translation companion (e.g. SKILL.ja.md) records, in its YAML frontmatter,
# the English source file and the git blob hash it was translated from:
#
#   ---
#   lang: ja
#   source: SKILL.md
#   source_sha: <output of `git hash-object SKILL.md` at translation time>
#   ---
#
# This script recomputes `git hash-object` for the current English file and compares it to the
# recorded source_sha. A blob hash only changes when the file content changes, so this flags a
# translation as STALE exactly when its English source was edited but the translation wasn't.
#
# Exit code: 0 = all up to date; 1 = at least one translation is stale or misconfigured.

set -uo pipefail
cd "$(git rev-parse --show-toplevel)" || exit 2

# read_fm <file> <key> : print the value of <key> from the leading YAML frontmatter block.
read_fm() {
  awk -v key="$2" '
    NR==1 { if ($0 != "---") exit; next }
    /^---[ \t]*$/ { exit }
    {
      if (index($0, key ":") == 1) {
        v = substr($0, length(key) + 2)
        gsub(/^[ \t]+/, "", v); gsub(/[ \t\r]+$/, "", v)
        print v; exit
      }
    }
  ' "$1"
}

status=0
found=0

while IFS= read -r ja; do
  found=1
  dir="$(dirname "$ja")"
  src="$(read_fm "$ja" source)"
  rec="$(read_fm "$ja" source_sha)"

  if [ -z "$src" ] || [ -z "$rec" ]; then
    printf 'MISCONFIG  %s  (missing source/source_sha frontmatter)\n' "$ja"
    status=1
    continue
  fi

  eng="$dir/$src"
  if [ ! -f "$eng" ]; then
    printf 'MISSING-EN %s  (source not found: %s)\n' "$ja" "$eng"
    status=1
    continue
  fi

  cur="$(git hash-object "$eng")"
  if [ "$cur" = "$rec" ]; then
    printf 'OK         %s\n' "$ja"
  else
    printf 'STALE      %s\n' "$ja"
    printf '           source=%s\n' "$eng"
    printf '           recorded=%s current=%s\n' "$rec" "$cur"
    printf '           -> re-translate from %s, then set: source_sha: %s\n' "$eng" "$cur"
    status=1
  fi
done < <(find . -name '*.ja.md' -not -path '*/.git/*' -not -path '*/node_modules/*' | sort)

if [ "$found" = 0 ]; then
  echo 'No *.ja.md translation files found.'
fi

exit "$status"
