#!/bin/zsh
set -euo pipefail

# ============================================
#  クラウド登録ランチャー
#  ダブルクリックで最新ジョブをGCSに登録
# ============================================

PROJECT_DIR="/Users/the1/projects/ラジオ動画ショート生成ツール"
cd "$PROJECT_DIR"

PYTHON_BIN=".venv/bin/python"

# .env 読み込み
if [ -f ".env" ]; then
  set -a
  source ".env"
  set +a
fi

echo "======================================"
echo "  ☁️  クラウド登録ツール"
echo "======================================"
echo ""

# runs/ 内のジョブを更新日時順に一覧
echo "📂 登録可能なジョブ一覧（最新順）:"
echo ""

JOBS=()
i=1
while IFS= read -r dir; do
  job_id=$(basename "$dir")
  # shorts_ フォルダ内の .mp4 ファイル数をカウント
  mp4_count=$(find "$dir" -maxdepth 2 -name "*.mp4" 2>/dev/null | wc -l | tr -d ' ')
  mod_date=$(stat -f "%Sm" -t "%m/%d %H:%M" "$dir")
  echo "  [$i] $job_id  (動画: ${mp4_count}本, 更新: $mod_date)"
  JOBS+=("$job_id")
  i=$((i + 1))
done < <(find "$PROJECT_DIR/runs" -mindepth 1 -maxdepth 1 -type d ! -name ".*" ! -name "zzztest" -print0 | xargs -0 ls -dt)

if [ ${#JOBS[@]} -eq 0 ]; then
  echo "  ジョブが見つかりません。先にGUIツールで動画を生成してください。"
  echo ""
  read "?Enterで終了"
  exit 1
fi

echo ""
echo "--------------------------------------"
echo ""

# ジョブ選択
echo -n "登録するジョブの番号を入力してください [1]: "
read choice
choice=${choice:-1}

# 入力チェック
if ! [[ "$choice" =~ ^[0-9]+$ ]] || [ "$choice" -lt 1 ] || [ "$choice" -gt ${#JOBS[@]} ]; then
  echo "❌ 無効な番号です。"
  read "?Enterで終了"
  exit 1
fi

SELECTED_JOB="${JOBS[$choice]}"
echo ""
echo "✅ 選択: $SELECTED_JOB"
echo ""

# まずドライラン
echo "📋 登録内容を確認中..."
echo ""
"$PYTHON_BIN" -m podcast_clip_factory.cli cloud-deploy --job-id "$SELECTED_JOB" --dry-run
echo ""

# 確認
echo "--------------------------------------"
echo -n "☁️  上記の内容でクラウドに登録しますか？ [Y/n]: "
read confirm
confirm=${confirm:-Y}

if [[ "$confirm" =~ ^[Yy]$ ]]; then
  echo ""
  echo "🚀 クラウドに登録中..."
  echo ""
  "$PYTHON_BIN" -m podcast_clip_factory.cli cloud-deploy --job-id "$SELECTED_JOB"
  echo ""
  echo "======================================"
  echo "  ✅ 登録完了！"
  echo "  毎日12:00に自動でYouTubeにアップロードされます。"
  echo "======================================"
else
  echo ""
  echo "キャンセルしました。"
fi

echo ""
read "?Enterで終了"
