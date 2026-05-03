#!/usr/bin/env bash
# Install HQ git hooks into .git/hooks/.
# Safe to re-run: backs up existing hooks before overwriting.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOOKS_SRC="$REPO_ROOT/scripts/hooks"
HOOKS_DST="$REPO_ROOT/.git/hooks"

for hook in "$HOOKS_SRC"/*; do
    name="$(basename "$hook")"
    dst="$HOOKS_DST/$name"
    if [ -f "$dst" ] && [ ! -L "$dst" ]; then
        mv "$dst" "${dst}.bak"
        echo "Backed up existing $name to ${dst}.bak"
    fi
    cp "$hook" "$dst"
    chmod +x "$dst"
    echo "Installed: .git/hooks/$name"
done

echo "HQ hooks installed."
