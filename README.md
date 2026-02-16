# ショート動画乱発ツール

Mac mini (Apple Silicon) 向けの「ショート動画乱発ツール」実装です。

## 仕様ハイライト
- 30〜50分の横長動画から 9:16 ショートを自動生成
- 目標 12 本、最低 10 本を保証
- クリップ長は 30〜60 秒
- レイアウトはクロップなしの上下帯スタイル
- ユーザー操作は最終チェックのみ（採用/除外、タイトル変更）
- 字幕焼き込みは既定で無効（元動画テロップを優先）
- Gemini候補抽出が失敗した場合は既定でジョブ失敗（機械的フォールバックを禁止）

## クイックスタート
1. 依存をインストール
```bash
pip install -e .[dev,transcribe,llm]
```
2. FFmpeg 7.x をインストール（videotoolbox有効版）
3. `.env.example` を `.env` にコピーして API キーを設定
4. GUI 起動
```bash
pcf
```

## 出力
- `runs/<job_id>/clips/*.mp4`
- `runs/<job_id>/metadata.json`
- `runs/<job_id>/transcript_full.json`

## 注意
- API キー未設定時はヒューリスティック選定に自動フォールバック
- `mlx-whisper` が失敗した場合は `faster-whisper` に自動切替
