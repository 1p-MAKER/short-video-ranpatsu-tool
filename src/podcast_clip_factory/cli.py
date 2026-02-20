from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path

from podcast_clip_factory.app import build_orchestrator


def _default_start_date() -> str:
    return (datetime.now().astimezone() + timedelta(days=1)).strftime("%Y-%m-%d")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pcf-youtube", description="YouTube予約実行 CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    run_cmd = sub.add_parser(
        "youtube-run",
        help="既存ジョブのYouTube予約を実行（GUI不要）",
    )
    run_cmd.add_argument("--job-id", default="", help="対象ジョブID（例: a1b2c3d4e5f6）")
    run_cmd.add_argument("--output-dir", default="", help="shorts_<job_id> 出力フォルダ")
    run_cmd.add_argument(
        "--max-items",
        type=int,
        default=1,
        help="1回の実行でアップロードする最大件数（既定: 1）",
    )
    run_cmd.add_argument(
        "--reset-failed",
        action="store_true",
        help="実行前に失敗分を再試行可能（planned）へ戻す",
    )
    run_cmd.add_argument(
        "--build-if-missing",
        action="store_true",
        help="予約キューが存在しない場合に新規作成する",
    )
    run_cmd.add_argument(
        "--start-date",
        default="",
        help="キュー新規作成時の開始日 YYYY-MM-DD（省略時は翌日）",
    )
    run_cmd.add_argument("--title-template", default="", help="キュー新規作成時のタイトルテンプレ")
    run_cmd.add_argument("--description-template", default="", help="キュー新規作成時の説明テンプレ")

    # Cloud Commands
    deploy_cmd = sub.add_parser(
        "cloud-deploy",
        help="指定ジョブをGCSへアップロードしFirestoreへ登録",
    )
    deploy_cmd.add_argument("--job-id", required=True, help="対象ジョブID")
    deploy_cmd.add_argument("--dry-run", action="store_true", help="GCS/Firestoreへの書き込みを行わない")

    worker_cmd = sub.add_parser(
        "cloud-worker",
        help="Firestoreキューズからタスクを取得してYouTubeへアップロード（Cloud Run用）",
    )
    worker_cmd.add_argument("--max-items", type=int, default=10, help="処理する最大件数 (default: 10)")
    worker_cmd.add_argument("--dry-run", action="store_true", help="YouTubeへの書き込みを行わない")

    return parser


def _resolve_job_id(orch, *, job_id: str, output_dir: str) -> str:
    resolved = job_id.strip()
    output = output_dir.strip()
    if output:
        payload = orch.attach_existing_output(Path(output))
        resolved = str(payload.get("job_id") or "").strip()
        print(f"既存出力を読み込み: {payload.get('final_dir')} (job={resolved})")
    if not resolved:
        raise RuntimeError("--job-id または --output-dir のどちらかを指定してください。")
    return resolved


def _cmd_youtube_run(args: argparse.Namespace) -> int:
    root_dir = Path(__file__).resolve().parents[2]
    orch = build_orchestrator(root_dir)
    job_id = _resolve_job_id(orch, job_id=str(args.job_id or ""), output_dir=str(args.output_dir or ""))

    if args.reset_failed:
        payload = orch.reset_failed_youtube_schedule(job_id)
        print(f"失敗分リセット: {int(payload.get('reset_count') or 0)}件")

    items = orch.list_youtube_schedule(job_id)
    if not items:
        if not args.build_if_missing:
            raise RuntimeError("予約キューがありません。GUIで予約キュー作成するか --build-if-missing を付けてください。")
        settings = orch.executor.settings
        start_date = str(args.start_date or "").strip() or _default_start_date()
        title_template = str(args.title_template or "").strip() or settings.youtube.title_template
        description_template = (
            str(args.description_template or "").strip() or settings.youtube.description_template
        )
        built = orch.build_youtube_schedule(
            job_id,
            start_date_str=start_date,
            title_template=title_template,
            description_template=description_template,
        )
        items = list(built.get("items") or [])
        print(f"予約キュー作成: {len(items)}件")

    result = orch.execute_youtube_schedule(
        job_id,
        on_log=lambda line: print(line),
        max_items=max(1, int(args.max_items or 1)),
    )
    scheduled_count = int(result.get("scheduled_count") or 0)
    failed_count = int(result.get("failed_count") or 0)
    print(f"YouTube予約実行完了: 成功 {scheduled_count}件 / 失敗 {failed_count}件")
    return 0


def _cmd_cloud_deploy(args: argparse.Namespace) -> int:
    from podcast_clip_factory.infrastructure.cloud.firestore_repo import FirestoreJobRepository
    from podcast_clip_factory.infrastructure.cloud.gcs_uploader import GCSUploader
    
    job_id = str(args.job_id).strip()
    if not job_id:
        raise ValueError("job_id is required")

    print(f"Cloud Deploy 開始: {job_id} (dry-run={args.dry_run})")
    
    root_dir = Path(__file__).resolve().parents[2]
    # Local orchestrator to read source data
    local_orch = build_orchestrator(root_dir)
    
    # 1. ローカルのスケジュール取得
    items = local_orch.repo.list_youtube_schedule(job_id)
    if not items:
        print("アップロード対象の予約アイテムがありません。")
        return 0
        
    print(f"対象アイテム数: {len(items)}")
    
    if args.dry_run:
        print("[DryRun] GCSアップロードとFirestore更新をスキップします。")
        return 0

    uploader = GCSUploader()
    firestore_repo = FirestoreJobRepository()
    
    # 2. 動画のGCSアップロード & uri更新
    uploaded_items = []
    for item in items:
        local_path = item.video_path
        if not local_path.exists():
            print(f"警告: ファイルが見つかりません {local_path} (skip)")
            continue
        
        blob_name = f"videos/{job_id}/{local_path.name}"
        print(f"Uploading {local_path.name} -> {blob_name} ...")
        gs_uri = uploader.upload_file(local_path, blob_name)
        
        # item.video_path を gs_uri に書き換える (domain modelは Path 型だが、ここでは str を入れるか Path(gs_uri) にする)
        # Path("gs://...") は動作するが、ローカルパスとしては無効。Firestoreには文字列として保存されるのでOK。
        item.video_path = Path(gs_uri)
        uploaded_items.append(item)
        
    if not uploaded_items:
        print("有効なアイテムがありませんでした。")
        return 1

    # 3. Firestoreへ登録
    print(f"Firestoreへスケジュール登録: {len(uploaded_items)}件 ...")
    firestore_repo.replace_youtube_schedule(job_id, uploaded_items)
    print("完了しました。")
    return 0


def _cmd_cloud_worker(args: argparse.Namespace) -> int:
    import tempfile
    from podcast_clip_factory.application.orchestrator import AppOrchestrator, PublishStatus
    from podcast_clip_factory.infrastructure.cloud.firestore_repo import FirestoreJobRepository
    from podcast_clip_factory.infrastructure.cloud.gcs_uploader import GCSUploader
    from podcast_clip_factory.infrastructure.publish.youtube_client import YouTubeUploadClient
    
    # 依存関係の注入
    # WorkerはSQLiteを使わない。ArtifactStoreも使わない(DLした一時ファイルのみ)。
    # しかし Orchestrator は repo, store, executor を要求する。
    # ここでは Orchestrator のロジックの一部 (execute_youtube_schedule) だけ再利用したいが、
    # 依存関係のセットアップが面倒なので、Worker専用の簡易ループを書く方が安全かつ確実。
    # Orchestrator は複雑なステート管理を含んでいるため。
    
    print(f"Cloud Worker 開始 (max_items={args.max_items}, dry-run={args.dry_run})")
    
    repo = FirestoreJobRepository()
    uploader = GCSUploader()
    
    # YouTube Client setup
    root_dir = Path(__file__).resolve().parents[2]
    # 設定読み込みのためにアプリのビルドプロセスを借用、あるいは直接envを読む
    # ここでは既存の仕組みに乗っかる
    local_orch = build_orchestrator(root_dir)
    settings = local_orch.executor.settings
    youtube_client = YouTubeUploadClient(
        client_id=settings.youtube.client_id,
        client_secret=settings.youtube.client_secret,
        refresh_token=settings.youtube.refresh_token,
    )
    
    # 1. Pendingタスクの取得 (global)
    # job_id 指定なしで全件取得したいが、repoのI/Fは job_id 引数がある。
    # 引数 None で全件取得できるように repo を修正した。
    pending = repo.list_youtube_schedule_by_status(
        job_id=None,
        statuses=(PublishStatus.PLANNED, PublishStatus.FAILED),
        limit=args.max_items
    )
    
    if not pending:
        print("処理待ちのタスクはありません。")
        return 0
        
    print(f"取得タスク数: {len(pending)}")
    
    if args.dry_run:
        print("[DryRun] YouTubeアップロードとFirestore更新をスキップします。")
        for item in pending:
            print(f"- {item.title} ({item.scheduled_at})")
        return 0

    # 2. 処理ループ
    success_count = 0
    fail_count = 0
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        for item in pending:
            print(f"Processing: {item.title} ({item.scheduled_at})")
            
            # 再試行上限チェック
            if item.attempts >= settings.youtube.max_retries:
                print(f"  Skip: Max retries exceeded ({item.attempts})")
                fail_count += 1
                continue
                
            try:
                # GCSからダウンロード
                local_video_path = tmp_path / f"{item.clip_id}.mp4"
                gs_uri = str(item.video_path)
                print(f"  Downloading {gs_uri} ...")
                uploader.download_file(gs_uri, local_video_path)
                
                # YouTubeアップロード
                print("  Uploading to YouTube ...")
                new_attempts = item.attempts + 1
                video_id, video_url = youtube_client.schedule_video(
                    video_path=local_video_path,
                    title=item.title,
                    description=item.description,
                    publish_at=item.scheduled_at,
                )
                
                # Firestore更新 (成功)
                print(f"  Success: {video_url}")
                repo.update_youtube_schedule_item(
                    schedule_id=item.schedule_id,
                    status=PublishStatus.SCHEDULED,
                    attempts=new_attempts,
                    youtube_video_id=video_id,
                    youtube_url=video_url,
                )
                success_count += 1
                
            except Exception as exc:
                err_msg = str(exc)
                print(f"  Failed: {err_msg}")
                # Firestore更新 (失敗)
                new_attempts = item.attempts + 1 # ここでインクリメントしておく
                repo.update_youtube_schedule_item(
                    schedule_id=item.schedule_id,
                    status=PublishStatus.FAILED,
                    attempts=new_attempts,
                    last_error=err_msg[:500]
                )
                fail_count += 1
                
                # クリティカルエラー判定 (Upload Limit / Auth)
                # Orchestratorのロジックを借用したいが、アクセスできないので簡易コピー
                lower_err = err_msg.lower()
                is_limit = any(x in lower_err for x in ("upload limit", "quotaexceeded"))
                is_auth = any(x in lower_err for x in ("invalid_grant", "invalid_client"))
                
                if is_limit or is_auth:
                    print(f"!! CRITICAL ERROR DETECTED: {err_msg} !!")
                    print("Aborting remaining tasks.")
                    break

    print(f"Worker完了: 成功 {success_count} / 失敗 {fail_count}")
    return 0 if fail_count == 0 else 1


def main() -> None:
    from dotenv import load_dotenv
    load_dotenv()
    parser = _build_parser()
    args = parser.parse_args()
    if args.command == "youtube-run":
        raise SystemExit(_cmd_youtube_run(args))
    elif args.command == "cloud-deploy":
        raise SystemExit(_cmd_cloud_deploy(args))
    elif args.command == "cloud-worker":
        raise SystemExit(_cmd_cloud_worker(args))
    raise SystemExit("unsupported command")


if __name__ == "__main__":
    main()
