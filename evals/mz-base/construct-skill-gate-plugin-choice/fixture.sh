#!/usr/bin/env bash
set -euo pipefail
# construct-skill finds its roots with git, and the eval workspace isn't a repository.
git init -q
git -c user.name=eval -c user.email=eval@example.invalid commit -q --allow-empty -m init

mkdir -p .claude-plugin
cat >.claude-plugin/marketplace.json <<'JSON'
{
  "name": "demo-marketplace",
  "owner": { "name": "eval" },
  "metadata": { "version": "0.1.0" },
  "plugins": [
    { "name": "team-core", "source": "./plugins/team-core", "category": "development", "keywords": ["workflow"] },
    { "name": "team-extra", "source": "./plugins/team-extra", "category": "development", "keywords": ["workflow"] }
  ]
}
JSON

# Two plugins with the same description, so no skill name favors one of them.
for plugin in team-core team-extra; do
  mkdir -p "plugins/$plugin/.claude-plugin" "plugins/$plugin/skills"
  touch "plugins/$plugin/skills/.gitkeep"
  cat >"plugins/$plugin/.claude-plugin/plugin.json" <<JSON
{
  "name": "$plugin",
  "version": "0.1.0",
  "description": "Developer workflow skills",
  "license": "MIT",
  "author": { "name": "eval" }
}
JSON
done
