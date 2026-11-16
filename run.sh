#!/bin/sh
# Local launcher: load secrets from .env (gitignored), then start the MCP server over stdio.
# Register with Claude Code using this script so the API key never goes into ~/.claude.json.
DIR="$(cd "$(dirname "$0")" && pwd)"
set -a; [ -f "$DIR/.env" ] && . "$DIR/.env"; set +a
: "${REFCONV_OUTPUT_DIR:=$DIR/streetview_images}"
export REFCONV_OUTPUT_DIR
cd "$DIR" || exit 1
exec "$DIR/.venv/bin/refconv-mcp" "$@"
