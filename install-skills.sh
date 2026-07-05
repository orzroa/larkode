#!/bin/bash
# Install Claude Code skills from larkode repo to ~/.claude/skills/

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_SOURCE="$SCRIPT_DIR/skills"
SKILLS_TARGET="$HOME/.claude/skills"

if [ ! -d "$SKILLS_SOURCE" ]; then
    echo "Error: skills directory not found at $SKILLS_SOURCE"
    exit 1
fi

mkdir -p "$SKILLS_TARGET"

for skill_dir in "$SKILLS_SOURCE"/*/; do
    if [ -d "$skill_dir" ]; then
        skill_name=$(basename "$skill_dir")
        target="$SKILLS_TARGET/$skill_name"
        echo "Installing skill: $skill_name"
        mkdir -p "$target"
        cp -r "$skill_dir"* "$target/"
    fi
done

echo "Done. Installed skills to $SKILLS_TARGET"
ls -1 "$SKILLS_TARGET"
