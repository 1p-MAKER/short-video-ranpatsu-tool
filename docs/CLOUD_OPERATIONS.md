# クラウド運用マニュアル 〜 デスクトップから始める YouTube 自動配信 〜

## 全体の流れ（概要）

```
① 動画を作る（GUIツール）
    ↓
② クラウドに登録する（ターミナルでコマンド1つ）
    ↓
③ あとは待つだけ（毎日12:00に自動アップロード）
```

---

## ① 動画を作る

### 1. GUIツールを起動する

Finder で以下の場所を開きます：

```
/Users/the1/projects/ラジオ動画ショート生成ツール/scripts/
```

**「Launch_Short_Video_Ranpatsu_Tool.command」** をダブルクリックします。

> 初回は「開いてもよろしいですか？」と聞かれることがあります → 「開く」をクリック。

### 2. GUIで動画を生成する

1. ラジオ音声ファイルを読み込みます
2. 各種設定（切り抜き箇所など）を指定します
3. 「生成」ボタンをクリックして動画を作成します
4. **完了したら、画面に表示される「ジョブID」をメモしてください**
   - 例: `a5555f7b817e`
   - これは `runs/` フォルダ内のフォルダ名でもあります

---

## ② クラウドに登録する

### 3. ターミナルを開く

以下のどちらかの方法でターミナルを開きます：
- **Spotlight**（`⌘ + Space`）で「ターミナル」と入力して起動
- **Finder** → アプリケーション → ユーティリティ → ターミナル

### 4. プロジェクトフォルダに移動する

ターミナルに以下をコピペして Enter：

```bash
cd /Users/the1/projects/ラジオ動画ショート生成ツール
```

### 5. 【確認】 登録内容をプレビューする（任意）

```bash
.venv/bin/python -m podcast_clip_factory.cli cloud-deploy --job-id ここにジョブID --dry-run
```

> `--dry-run` を付けると、実際にはアップロードせずに内容だけ確認できます。

### 6. 【実行】 クラウドに登録する

```bash
.venv/bin/python -m podcast_clip_factory.cli cloud-deploy --job-id ここにジョブID
```

> 実行例:
> ```bash
> .venv/bin/python -m podcast_clip_factory.cli cloud-deploy --job-id a5555f7b817e
> ```

以下のことが自動的に行われます：
- 動画ファイル → Google Cloud Storage にアップロード
- 配信スケジュール → Firestore（データベース）にキュー登録

**「完了しました。」** と表示されたら成功です！

---

## ③ あとは待つだけ（自動）

**毎日12:00（正午）** に、クラウド上の Worker が自動起動します：

1. Firestore から「配信待ち」のタスクを最大10件取得
2. GCS から動画をダウンロード
3. YouTube に予約アップロード（設定された配信日時で公開）
4. ステータスを「scheduled（予約済み）」に更新

**あなたは何もしなくてOKです。**

---

## 📌 よくある操作

### 状況を確認したいとき

```bash
cd /Users/the1/projects/ラジオ動画ショート生成ツール
.venv/bin/python -m podcast_clip_factory.cli cloud-worker --dry-run
```

→ 配信待ちのタスク一覧と配信予定日時が表示されます。

### 手動で今すぐアップロードしたいとき

```bash
cd /Users/the1/projects/ラジオ動画ショート生成ツール
.venv/bin/python -m podcast_clip_factory.cli cloud-worker
```

→ Worker を今すぐ実行し、YouTube に予約アップロードします。

### 失敗したタスクを再試行したいとき

Gemini に「failed のタスクをリセットして」と伝えてください。
ステータスを `planned` に戻せば、次回の Worker 実行時に再処理されます。

---

## ⚠️ 注意事項

- **1日の最大アップロード件数**: 10件（YouTube API制限対策）
- **ジョブID** は画面またはフォルダ名で確認できます（`runs/` の中）
- 動画ファイルのサイズが大きいと `cloud-deploy` に時間がかかります（1件あたり数十秒〜数分）
