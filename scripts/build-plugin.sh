#!/usr/bin/env bash
# Sync skills and templates into plugin/ so it is a complete, installable package.
# Usage:
#   ./scripts/build-plugin.sh           # local dev — no version injection
#   ./scripts/build-plugin.sh 3         # CI — injects version into plugin.json
set -euo pipefail

VERSION="${1:-}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Syncing skills and templates into plugin/ ..."

rm -rf "$REPO_ROOT/plugin/skills" "$REPO_ROOT/plugin/templates" "$REPO_ROOT/plugin/scripts"
mkdir -p "$REPO_ROOT/plugin/skills"
mkdir -p "$REPO_ROOT/plugin/templates"
mkdir -p "$REPO_ROOT/plugin/scripts"

cp -r "$REPO_ROOT/.claude/skills/coquill"              "$REPO_ROOT/plugin/skills/"
cp -r "$REPO_ROOT/.claude/skills/coquill-analyzer"    "$REPO_ROOT/plugin/skills/"
cp -r "$REPO_ROOT/.claude/skills/coquill-renderer"    "$REPO_ROOT/plugin/skills/"
cp -r "$REPO_ROOT/.claude/skills/coquill-transcriber" "$REPO_ROOT/plugin/skills/"
cp -r "$REPO_ROOT/templates/_examples"             "$REPO_ROOT/plugin/templates/"
cp "$REPO_ROOT/scripts/analyze.py"                 "$REPO_ROOT/plugin/scripts/"
cp "$REPO_ROOT/scripts/render.py"                  "$REPO_ROOT/plugin/scripts/"

if [[ -n "$VERSION" ]]; then
  echo "Injecting version $VERSION ..."
  sed -i.bak "s/\"0\.0\.0\"/\"${VERSION}\"/" "$REPO_ROOT/plugin/.claude-plugin/plugin.json"
  rm "$REPO_ROOT/plugin/.claude-plugin/plugin.json.bak"
fi

echo "Done. Plugin ready at plugin/"
