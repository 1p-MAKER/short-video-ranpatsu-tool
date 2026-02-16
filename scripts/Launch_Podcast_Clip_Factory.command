#!/bin/zsh
set -euo pipefail

PROJECT_DIR="/Users/the1/projects/ラジオ動画ショート生成ツール"
cd "$PROJECT_DIR"

if [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
fi

PYTHON_BIN="python3"
if [ -x ".venv/bin/python" ]; then
  PYTHON_BIN=".venv/bin/python"
fi

if ! "$PYTHON_BIN" -c "import flet" >/dev/null 2>&1; then
  echo "Flet が見つかりません。先に依存関係をインストールしてください:"
  echo "  cd '$PROJECT_DIR'"
  echo "  pip install -e .[dev,transcribe,llm]"
  echo
  read "?Enterで終了"
  exit 1
fi

PYTHONPATH="$PROJECT_DIR/src:${PYTHONPATH:-}" "$PYTHON_BIN" -m podcast_clip_factory.app || {
  echo
  echo "起動に失敗しました。ログを確認してください。"
  read "?Enterで終了"
  exit 1
}
