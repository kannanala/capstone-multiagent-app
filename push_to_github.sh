#!/usr/bin/env bash
# push_to_github.sh
# Stages, commits, and pushes index.html to the configured GitHub repo.
# Called automatically by multi_agent.py / multi_agent_local.py on APPROVED.
set -e

# Load values from .env if present
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

REPO_URL="${GITHUB_REPO_URL:-}"
BRANCH="${GITHUB_BRANCH:-main}"
FILE="index.html"

if [ -z "$REPO_URL" ]; then
    echo "[✗] GITHUB_REPO_URL is not set. Update your .env file."
    exit 1
fi

if [ ! -f "$FILE" ]; then
    echo "[✗] $FILE not found. Nothing to push."
    exit 1
fi

echo "[push_to_github] Staging $FILE ..."
git add "$FILE"

echo "[push_to_github] Committing ..."
git commit -m "Auto-push approved app [$(date -u '+%Y-%m-%dT%H:%M:%SZ')]" || echo "[!] Nothing new to commit."

echo "[push_to_github] Pushing to $BRANCH ..."
git push "$REPO_URL" HEAD:"$BRANCH"

echo "[push_to_github] Done ✓"
