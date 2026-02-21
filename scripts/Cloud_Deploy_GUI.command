#!/bin/zsh
set -euo pipefail
PROJECT_DIR="/Users/the1/projects/ラジオ動画ショート生成ツール"
cd "$PROJECT_DIR"
PYTHON_BIN=".venv/bin/python"
PYTHONPATH="$PROJECT_DIR/src:${PYTHONPATH:-}" "$PYTHON_BIN" -m podcast_clip_factory.cloud_deploy_app
