from __future__ import annotations

import json
import subprocess
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import unquote, urlparse

import flet as ft

from podcast_clip_factory.domain.models import ReviewDecision
from podcast_clip_factory.presentation.progress_view import ProgressView
from podcast_clip_factory.presentation.result_view import ResultView
from podcast_clip_factory.presentation.review_view import ReviewView


class MainView(ft.Column):
    DEFAULT_PICK_DIR = Path("/Volumes/1peiHDD_2TB/DaVinciResolve_material_HDD/RADIO")

    def __init__(self, page: ft.Page, orchestrator, logger, initial_video: Path | None = None) -> None:
        self._page = page
        self.orchestrator = orchestrator
        self.logger = logger

        self.selected_video: Path | None = None
        self.current_job_id: str | None = None
        self._last_final_dir: Path | None = None
        self._worker_thread: threading.Thread | None = None
        self._heartbeat_thread: threading.Thread | None = None
        self._heartbeat_stop = threading.Event()
        self._job_running = False
        self._job_started_at = 0.0
        self._last_progress_at = 0.0
        self._last_progress_message = ""
        self._log_lines: list[str] = []
        self._final_payload: dict | None = None

        settings = orchestrator.executor.settings
        configured_default_dir = str(settings.app.default_media_dir or "").strip()
        self._default_media_dir = (
            Path(configured_default_dir).expanduser() if configured_default_dir else self.DEFAULT_PICK_DIR
        )

        self.file_picker = ft.FilePicker()
        self._page.services.append(self.file_picker)

        self.path_text = ft.Text("動画未選択", size=13)
        self.pick_button = ft.ElevatedButton("動画を選択", on_click=self._on_pick_clicked)
        self.start_button = ft.ElevatedButton("自動生成を開始", disabled=True, on_click=self._on_start, visible=False)
        self.resume_output_button = ft.OutlinedButton("既存出力から予約再開", on_click=self._on_resume_output_clicked)
        self.stop_button = ft.ElevatedButton("停止", disabled=True, on_click=self._on_stop)

        self.progress_view = ProgressView()
        self.runtime_text = ft.Text("稼働状態: 待機", size=13, color=ft.Colors.BLUE_GREY_700)
        self.estimate_text = ft.Text("目安: 50分動画で約15〜25分", size=12, color=ft.Colors.BLUE_GREY_500)
        self.log_box = ft.TextField(
            label="処理ログ（最新100行）",
            value="",
            read_only=True,
            multiline=True,
            min_lines=4,
            max_lines=6,
        )
        self.review_view = ReviewView()
        self.result_view = ResultView()
        self.open_output_button = ft.OutlinedButton(
            "出力フォルダを開く",
            visible=False,
            on_click=self._on_open_output,
        )

        # YouTube予約セクション
        default_start_date = (datetime.now().astimezone() + timedelta(days=1)).strftime("%Y-%m-%d")
        self.youtube_start_date_field = ft.TextField(
            label="開始日 (YYYY-MM-DD)",
            value=default_start_date,
            width=190,
            text_size=12,
            content_padding=8,
        )
        self.youtube_title_template_field = ft.TextField(
            label="タイトルテンプレ",
            value=settings.youtube.title_template,
            width=320,
            text_size=12,
            content_padding=8,
        )
        self.youtube_description_template_field = ft.TextField(
            label="説明テンプレ",
            value=settings.youtube.description_template,
            multiline=True,
            min_lines=2,
            max_lines=3,
            text_size=12,
            content_padding=8,
            expand=True,
        )
        self.youtube_build_button = ft.ElevatedButton(
            "予約キュー作成",
            on_click=self._on_build_youtube_schedule,
            disabled=True,
        )
        self.youtube_execute_button = ft.ElevatedButton(
            "YouTube予約を実行",
            on_click=self._on_execute_youtube_schedule,
            disabled=True,
        )
        self.youtube_reset_failed_button = ft.OutlinedButton(
            "失敗分を再試行可能に戻す",
            on_click=self._on_reset_failed_youtube_schedule,
            disabled=True,
        )
        self.youtube_refresh_button = ft.OutlinedButton(
            "予約状況を更新",
            on_click=self._on_refresh_youtube_schedule,
            disabled=True,
        )
        self.cloud_deploy_button = ft.ElevatedButton(
            "☁️ クラウドに登録",
            on_click=self._on_cloud_deploy,
            disabled=True,
            color=ft.Colors.WHITE,
            bgcolor="#6C63FF",
        )
        self.cloud_deploy_status = ft.Text("", size=11, color=ft.Colors.BLUE_GREY_600)
        self.youtube_status_text = ft.Text("予約キュー未作成", size=12, color=ft.Colors.BLUE_GREY_600)
        self.youtube_calendar_view = ft.Column(spacing=6, height=240, scroll=ft.ScrollMode.AUTO)
        slot_label = " / ".join(f"{hour:02d}:00" for hour in settings.youtube.slot_hours)
        self.youtube_panel = ft.Container(
            visible=False,
            padding=10,
            border=ft.border.all(1, ft.Colors.BLUE_GREY_200),
            border_radius=8,
            content=ft.Column(
                spacing=8,
                controls=[
                    ft.Text("YouTube予約投稿", size=14, weight=ft.FontWeight.W_600),
                    ft.Text(f"投稿スロット: 毎日 {slot_label}", size=11, color=ft.Colors.BLUE_GREY_600),
                    ft.Row(
                        spacing=8,
                        controls=[
                            self.youtube_start_date_field,
                            self.youtube_title_template_field,
                            ft.Container(expand=True, content=self.youtube_description_template_field),
                        ],
                    ),
                    ft.Row(
                        spacing=8,
                        controls=[
                            self.youtube_build_button,
                            self.youtube_execute_button,
                            self.youtube_reset_failed_button,
                            self.youtube_refresh_button,
                        ],
                    ),
                    self.youtube_status_text,
                    ft.Divider(height=1, color=ft.Colors.BLUE_GREY_200),
                    ft.Row(
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            self.cloud_deploy_button,
                            self.cloud_deploy_status,
                        ],
                    ),
                    ft.Divider(height=1, color=ft.Colors.BLUE_GREY_200),
                    ft.Text("予約カレンダー", size=12, weight=ft.FontWeight.W_500),
                    self.youtube_calendar_view,
                ],
            ),
        )

        self.submit_button = ft.ElevatedButton("この内容で確定出力", visible=False, on_click=self._on_submit)
        self.snack = ft.SnackBar(ft.Text(""))
        self._page.overlay.append(self.snack)

        super().__init__(
            controls=[
                ft.Text("ショート動画乱発ツール", size=24, weight=ft.FontWeight.BOLD),
                ft.Text("開始から最終チェック手前まで全自動。最後だけ手動確認。", size=13),
                ft.Text("起動直後のドロップ画面で動画を落とすと自動開始（または「動画を選択」）", size=11, color=ft.Colors.BLUE_GREY_600),
                ft.Row([self.pick_button, self.resume_output_button, self.stop_button], spacing=10),
                self.path_text,
                ft.Divider(),
                self.progress_view,
                self.runtime_text,
                self.estimate_text,
                ft.Divider(),
                self.review_view,
                self.submit_button,
                ft.Divider(),
                self.result_view,
                self.open_output_button,
                self.youtube_panel,
                ft.Divider(),
                self.log_box,
            ],
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
        )

        if initial_video and initial_video.exists():
            self.selected_video = initial_video
            self.path_text.value = f"選択中: {self.selected_video}"
            self._append_log(f"D&D入力を受け取りました: {self.selected_video}")
            self._on_start(None)

    def on_window_event(self, event: ft.WindowEvent) -> None:
        event_type = getattr(getattr(event, "type", None), "value", str(getattr(event, "type", "")))
        dropped = self._extract_dropped_paths(event_type=event_type, payload=getattr(event, "data", None))
        if not dropped:
            if "drop" in event_type.lower() or "file" in event_type.lower():
                self._append_log(f"D&Dイベント受信: type={event_type}, data={str(getattr(event, 'data', ''))[:180]}")
            return
        self._handle_dropped_file(dropped[0])

    def _handle_dropped_file(self, file_path: Path) -> None:
        if self._job_running:
            self._toast("ジョブ実行中は新しい動画を受け付けできません")
            return
        if not file_path.exists() or not file_path.is_file():
            self._toast(f"ドロップされたファイルを確認できません: {file_path}")
            return
        self.selected_video = file_path
        self.path_text.value = f"選択中: {self.selected_video}"
        self._append_log(f"ドロップで動画選択: {self.selected_video}")
        self._page.update()
        self._on_start(None)

    def _extract_dropped_paths(self, *, event_type: str, payload) -> list[Path]:
        normalized_event_type = str(event_type or "").lower()
        if "drop" not in normalized_event_type and "file" not in normalized_event_type:
            # Some runtimes may still send file payloads without explicit type naming.
            if payload is None:
                return []

        def maybe_to_path(value: str) -> Path | None:
            text = value.strip().strip('"').strip("'")
            if not text:
                return None
            if text.startswith("file://"):
                parsed = urlparse(text)
                text = unquote(parsed.path or "")
            if text.startswith("/"):
                candidate = Path(text).expanduser()
                if candidate.exists() and candidate.is_file():
                    return candidate
            return None

        def walk(value, output: list[Path]) -> None:
            if value is None:
                return
            if isinstance(value, (list, tuple)):
                for item in value:
                    walk(item, output)
                return
            if isinstance(value, dict):
                for key in ("path", "paths", "file", "files", "value", "data", "items"):
                    if key in value:
                        walk(value[key], output)
                for item in value.values():
                    walk(item, output)
                return
            if isinstance(value, str):
                # JSON payload from some runtimes.
                trimmed = value.strip()
                if trimmed.startswith("{") or trimmed.startswith("["):
                    try:
                        walk(json.loads(trimmed), output)
                        return
                    except Exception:
                        pass

                # Multi-path payloads might be newline/comma separated.
                chunks = [trimmed]
                if "\n" in trimmed:
                    chunks = [c for c in trimmed.splitlines() if c.strip()]
                elif "," in trimmed and "file://" in trimmed:
                    chunks = [c for c in trimmed.split(",") if c.strip()]

                for chunk in chunks:
                    p = maybe_to_path(chunk)
                    if p is not None:
                        output.append(p)

        found: list[Path] = []
        walk(payload, found)

        # Keep input order while removing duplicates.
        deduped: list[Path] = []
        seen: set[str] = set()
        for path in found:
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            deduped.append(path)
        return deduped

    async def _on_pick_clicked(self, _: ft.ControlEvent) -> None:
        initial_dir = str(self._default_media_dir or self.DEFAULT_PICK_DIR)
        files = await self.file_picker.pick_files(
            allow_multiple=False,
            initial_directory=initial_dir,
        )
        if not files:
            return
        self.selected_video = Path(files[0].path)
        self.path_text.value = f"選択中: {self.selected_video}"
        self._page.update()
        self._on_start(None)

    async def _on_resume_output_clicked(self, _: ft.ControlEvent) -> None:
        if self._job_running:
            self._toast("ジョブ実行中は再開できません")
            return
        initial_dir = str(self._default_media_dir or self.DEFAULT_PICK_DIR)
        directory = await self.file_picker.get_directory_path(
            dialog_title="既存の出力フォルダを選択",
            initial_directory=initial_dir,
        )
        if not directory:
            return
        try:
            payload = self.orchestrator.attach_existing_output(Path(directory))
        except Exception as exc:
            self._toast(str(exc))
            self._append_log(f"既存出力の再開に失敗: {exc}")
            self._page.update()
            return

        self.current_job_id = str(payload.get("job_id") or "")
        self._last_final_dir = Path(str(payload.get("final_dir") or directory))
        clip_count = int(payload.get("clip_count") or 0)
        self.result_view.set_result(clip_count, str(self._last_final_dir))
        self.open_output_button.visible = True

        self._enable_youtube_panel(
            items=list(payload.get("items") or []),
            message=f"既存出力を読み込みました: job={self.current_job_id} / クリップ{clip_count}件",
        )
        self._append_log(f"既存出力を読み込みました: {self._last_final_dir}")
        self._page.update()

    def _on_start(self, _: ft.ControlEvent | None) -> None:
        if self._job_running:
            return

        preflight_errors = self.orchestrator.preflight(self.selected_video)
        if preflight_errors:
            self._toast(preflight_errors[0])
            for err in preflight_errors:
                self._append_log(f"開始前チェック失敗: {err}")
            return

        self.start_button.disabled = True
        self.pick_button.disabled = True
        self.resume_output_button.disabled = True
        self.stop_button.disabled = False
        self.submit_button.visible = False
        self.review_view.controls.clear()
        self.result_view.summary.value = ""
        self.result_view.path_text.value = ""
        self._last_final_dir = None
        self._final_payload = None
        self.open_output_button.visible = False
        self.youtube_panel.visible = False
        self.youtube_build_button.disabled = True
        self.youtube_execute_button.disabled = True
        self.youtube_reset_failed_button.disabled = True
        self.youtube_refresh_button.disabled = True
        self.youtube_calendar_view.controls.clear()
        self.youtube_status_text.value = "予約キュー未作成"
        self._log_lines = []
        self.log_box.value = ""
        self._last_progress_message = ""
        self.progress_view.set("ジョブ開始", 0.01)
        self._set_running(True)
        self._append_log("ジョブを開始しました")
        self._page.update()

        def worker() -> None:
            try:
                result = self.orchestrator.run_pipeline(
                    self.selected_video,
                    on_progress=lambda msg, p: self._dispatch_ui(self._update_progress, msg, p),
                    on_log=lambda line: self._dispatch_ui(self._append_log, line),
                )
                rows = self.orchestrator.get_review_rows(result.job.job_id)
                self.current_job_id = result.job.job_id
                self._dispatch_ui(self._show_review_rows, rows)
            except Exception as exc:
                self.logger.exception("ui.pipeline_failed", error=str(exc))
                self._dispatch_ui(self._on_error, str(exc))

        self._worker_thread = threading.Thread(target=worker, daemon=True)
        self._worker_thread.start()

    def _update_progress(self, message: str, value: float) -> None:
        self._last_progress_at = time.time()
        self.progress_view.set(message, value)
        if message != self._last_progress_message:
            self._append_log(f"進捗更新: {message} ({int(value * 100)}%)")
            self._last_progress_message = message
        self._page.update()

    def _show_review_rows(self, rows: list[dict]) -> None:
        self.review_view.load_rows(rows)
        self.submit_button.visible = True
        self.progress_view.set("最終チェックで採用可否・タイトルを確認してください", 1.0)
        self._append_log("最終チェックに進みました")
        self._set_running(False)
        self._page.update()

    def _on_submit(self, _: ft.ControlEvent) -> None:
        if not self.current_job_id:
            self._toast("ジョブが存在しません")
            return

        decisions: list[ReviewDecision] = self.review_view.collect_decisions()
        title_style = self.review_view.collect_title_style()
        impact_style = self.review_view.collect_impact_style()
        impact_texts = self.review_view.collect_impact_phrases()
        self.submit_button.disabled = True
        self.start_button.disabled = True
        self.pick_button.disabled = True
        self.stop_button.disabled = False
        self.progress_view.set("確定出力レンダリング中", 0.99)
        self._append_log("確定出力を開始しました（タイトル編集内容を反映）")
        self._set_running(True)
        self._page.update()

        def worker() -> None:
            try:
                payload = self.orchestrator.finalize_review(
                    self.current_job_id,
                    decisions,
                    title_style=title_style,
                    impact_style=impact_style,
                    impact_texts=impact_texts,
                    on_log=lambda line: self._dispatch_ui(self._append_log, line),
                )
                self._dispatch_ui(self._on_submit_success, payload)
            except Exception as exc:
                self.logger.exception("ui.finalize_failed", error=str(exc))
                self._dispatch_ui(self._on_error, str(exc))

        self._worker_thread = threading.Thread(target=worker, daemon=True)
        self._worker_thread.start()

    def _on_submit_success(self, payload: dict) -> None:
        if not self.current_job_id:
            self._on_error("ジョブ情報が見つかりません")
            return
        final_dir = Path(payload.get("final_dir") or self.orchestrator.store.final_dir(self.current_job_id))
        self._last_final_dir = final_dir
        self._final_payload = payload
        self.result_view.set_result(payload["selected_count"], str(final_dir))
        self.open_output_button.visible = True
        self.start_button.disabled = False
        self.pick_button.disabled = False
        self.resume_output_button.disabled = False
        self.stop_button.disabled = True
        self.submit_button.visible = False
        self.submit_button.disabled = False
        self.progress_view.set("確定出力が完了しました", 1.0)
        self._set_running(False)
        self._toast("確定出力が完了しました")
        self._open_output_folder()

        # YouTube予約を有効化
        self._enable_youtube_panel(items=[], message="開始日を入れて「予約キュー作成」を押してください。")
        self._page.update()

    def _enable_youtube_panel(self, *, items: list[dict], message: str) -> None:
        self.youtube_panel.visible = True
        self.youtube_build_button.disabled = False
        self.youtube_refresh_button.disabled = False
        self.youtube_execute_button.disabled = len(items) == 0
        self.youtube_reset_failed_button.disabled = self._count_failed_items(items) == 0
        self.cloud_deploy_button.disabled = len(items) == 0
        self.youtube_status_text.value = message
        self._render_youtube_calendar(items)

    def _on_build_youtube_schedule(self, _: ft.ControlEvent) -> None:
        if not self.current_job_id:
            self._toast("ジョブが存在しません")
            return
        self.youtube_build_button.disabled = True
        self.youtube_execute_button.disabled = True
        self.youtube_reset_failed_button.disabled = True
        self.youtube_refresh_button.disabled = True
        self._append_log("YouTube予約キューを作成します")
        self._page.update()

        start_date = (self.youtube_start_date_field.value or "").strip()
        title_template = (self.youtube_title_template_field.value or "").strip() or "{title}"
        desc_template = (self.youtube_description_template_field.value or "").strip()

        def worker() -> None:
            try:
                payload = self.orchestrator.build_youtube_schedule(
                    self.current_job_id,
                    start_date_str=start_date,
                    title_template=title_template,
                    description_template=desc_template,
                )
                self._dispatch_ui(self._on_build_youtube_schedule_success, payload)
            except Exception as exc:
                self.logger.exception("ui.youtube_schedule_build_failed", error=str(exc))
                self._dispatch_ui(self._on_youtube_action_error, str(exc))

        self._worker_thread = threading.Thread(target=worker, daemon=True)
        self._worker_thread.start()

    def _on_build_youtube_schedule_success(self, payload: dict) -> None:
        items = payload.get("items") or []
        self.youtube_status_text.value = f"予約キューを作成しました: {len(items)}件"
        self.youtube_build_button.disabled = False
        self.youtube_execute_button.disabled = len(items) == 0
        self.youtube_reset_failed_button.disabled = self._count_failed_items(items) == 0
        self.youtube_refresh_button.disabled = False
        self._render_youtube_calendar(items)
        self._append_log(f"YouTube予約キュー作成完了: {len(items)}件")
        self._page.update()

    def _on_execute_youtube_schedule(self, _: ft.ControlEvent) -> None:
        if not self.current_job_id:
            self._toast("ジョブが存在しません")
            return
        self.youtube_build_button.disabled = True
        self.youtube_execute_button.disabled = True
        self.youtube_reset_failed_button.disabled = True
        self.youtube_refresh_button.disabled = True
        self._append_log("YouTube予約を実行します")
        self._page.update()

        def worker() -> None:
            try:
                payload = self.orchestrator.execute_youtube_schedule(
                    self.current_job_id,
                    on_log=lambda line: self._dispatch_ui(self._append_log, line),
                )
                self._dispatch_ui(self._on_execute_youtube_schedule_success, payload)
            except Exception as exc:
                self.logger.exception("ui.youtube_schedule_execute_failed", error=str(exc))
                self._dispatch_ui(self._on_youtube_action_error, str(exc))

        self._worker_thread = threading.Thread(target=worker, daemon=True)
        self._worker_thread.start()

    def _on_execute_youtube_schedule_success(self, payload: dict) -> None:
        scheduled_count = int(payload.get("scheduled_count") or 0)
        failed_count = int(payload.get("failed_count") or 0)
        items = payload.get("items") or []
        self.youtube_status_text.value = (
            f"YouTube予約結果: 成功 {scheduled_count}件 / 失敗 {failed_count}件"
        )
        self.youtube_build_button.disabled = False
        self.youtube_execute_button.disabled = False
        self.youtube_reset_failed_button.disabled = self._count_failed_items(items) == 0
        self.youtube_refresh_button.disabled = False
        self._render_youtube_calendar(items)
        self._append_log(
            f"YouTube予約実行完了: 成功 {scheduled_count}件 / 失敗 {failed_count}件"
        )
        self._page.update()

    def _on_reset_failed_youtube_schedule(self, _: ft.ControlEvent) -> None:
        if not self.current_job_id:
            self._toast("ジョブが存在しません")
            return
        self.youtube_build_button.disabled = True
        self.youtube_execute_button.disabled = True
        self.youtube_reset_failed_button.disabled = True
        self.youtube_refresh_button.disabled = True
        self._append_log("YouTube予約の失敗分を再試行可能に戻します")
        self._page.update()

        def worker() -> None:
            try:
                payload = self.orchestrator.reset_failed_youtube_schedule(self.current_job_id)
                self._dispatch_ui(self._on_reset_failed_youtube_schedule_success, payload)
            except Exception as exc:
                self.logger.exception("ui.youtube_schedule_reset_failed", error=str(exc))
                self._dispatch_ui(self._on_youtube_action_error, str(exc))

        self._worker_thread = threading.Thread(target=worker, daemon=True)
        self._worker_thread.start()

    def _on_reset_failed_youtube_schedule_success(self, payload: dict) -> None:
        reset_count = int(payload.get("reset_count") or 0)
        items = payload.get("items") or []
        self.youtube_status_text.value = f"失敗分を再試行可能に戻しました: {reset_count}件"
        self.youtube_build_button.disabled = False
        self.youtube_execute_button.disabled = len(items) == 0
        self.youtube_reset_failed_button.disabled = self._count_failed_items(items) == 0
        self.youtube_refresh_button.disabled = False
        self._render_youtube_calendar(items)
        self._append_log(f"YouTube予約 失敗分リセット完了: {reset_count}件")
        self._page.update()

    def _on_refresh_youtube_schedule(self, _: ft.ControlEvent) -> None:
        if not self.current_job_id:
            return
        try:
            items = self.orchestrator.list_youtube_schedule(self.current_job_id)
            self._render_youtube_calendar(items)
            self.youtube_status_text.value = f"予約状況を更新しました: {len(items)}件"
            self.youtube_reset_failed_button.disabled = self._count_failed_items(items) == 0
            self._append_log("YouTube予約状況を更新しました")
            self._page.update()
        except Exception as exc:
            self._on_youtube_action_error(str(exc))

    def _on_cloud_deploy(self, _: ft.ControlEvent) -> None:
        if not self.current_job_id:
            self._toast("ジョブが存在しません")
            return
        self.cloud_deploy_button.disabled = True
        self.cloud_deploy_status.value = "☁️ アップロード中..."
        self.cloud_deploy_status.color = "#FBBF24"
        self._append_log("クラウド登録を開始します")
        self._page.update()

        def worker() -> None:
            try:
                from podcast_clip_factory.infrastructure.cloud.firestore_repo import FirestoreJobRepository
                from podcast_clip_factory.infrastructure.cloud.gcs_uploader import GCSUploader

                items = self.orchestrator.repo.list_youtube_schedule(self.current_job_id)
                if not items:
                    self._dispatch_ui(self._on_cloud_deploy_done, False, "アイテムがありません")
                    return

                uploader = GCSUploader()
                firestore_repo = FirestoreJobRepository()
                uploaded = []

                for i, item in enumerate(items):
                    local_path = item.video_path
                    if not local_path.exists():
                        self._dispatch_ui(self._append_log, f"⚠️ スキップ: {local_path.name}")
                        continue
                    blob_name = f"videos/{self.current_job_id}/{local_path.name}"
                    self._dispatch_ui(self._append_log, f"[{i+1}/{len(items)}] {local_path.name}")
                    gs_uri = uploader.upload_file(local_path, blob_name)
                    item.video_path = Path(gs_uri)
                    uploaded.append(item)

                if not uploaded:
                    self._dispatch_ui(self._on_cloud_deploy_done, False, "有効なファイルがありません")
                    return

                firestore_repo.replace_youtube_schedule(self.current_job_id, uploaded)
                self._dispatch_ui(
                    self._on_cloud_deploy_done, True,
                    f"{len(uploaded)}件をクラウドに登録しました！",
                )
            except Exception as exc:
                self._dispatch_ui(self._on_cloud_deploy_done, False, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _on_cloud_deploy_done(self, success: bool, message: str) -> None:
        self.cloud_deploy_button.disabled = False
        if success:
            self.cloud_deploy_status.value = f"✅ {message}"
            self.cloud_deploy_status.color = "#4ADE80"
            self._append_log(f"クラウド登録完了: {message}")
            self._toast(f"クラウド登録完了: {message}")
        else:
            self.cloud_deploy_status.value = f"❌ {message}"
            self.cloud_deploy_status.color = "#F87171"
            self._append_log(f"クラウド登録エラー: {message}")
            self._toast(f"クラウド登録失敗: {message}")
        self._page.update()

    def _render_youtube_calendar(self, items: list[dict]) -> None:
        self.youtube_calendar_view.controls.clear()
        if not items:
            self.youtube_calendar_view.controls.append(ft.Text("予約データがありません", size=11))
            return

        grouped: dict[str, list[dict]] = {}
        for item in items:
            scheduled_at = str(item.get("scheduled_at") or "")
            try:
                dt = datetime.fromisoformat(scheduled_at)
                day = dt.strftime("%Y-%m-%d")
                item["_display_time"] = dt.strftime("%H:%M")
            except Exception:
                day = "不明日付"
                item["_display_time"] = "--:--"
            grouped.setdefault(day, []).append(item)

        for day in sorted(grouped.keys()):
            rows: list[ft.Control] = []
            for item in grouped[day]:
                status = str(item.get("status") or "planned")
                status_text, status_color = self._map_schedule_status(status)
                title = str(item.get("title") or "")
                video_id = str(item.get("youtube_video_id") or "")
                attempts = int(item.get("attempts") or 0)
                line = ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text(str(item.get("_display_time") or "--:--"), width=48, size=11),
                        ft.Container(
                            content=ft.Text(status_text, size=10, color=ft.Colors.WHITE),
                            bgcolor=status_color,
                            border_radius=4,
                            padding=ft.padding.symmetric(horizontal=6, vertical=2),
                        ),
                        ft.Text(title, size=11, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(
                            f"試行{attempts}" + (f" / {video_id}" if video_id else ""),
                            size=10,
                            color=ft.Colors.BLUE_GREY_500,
                        ),
                    ],
                )
                rows.append(line)
                if status == "failed":
                    error_text = str(item.get("last_error") or "").strip()
                    if error_text:
                        rows.append(
                            ft.Text(
                                f"エラー: {error_text[:160]}",
                                size=10,
                                color=ft.Colors.RED_500,
                            )
                        )

            self.youtube_calendar_view.controls.append(
                ft.Container(
                    padding=8,
                    border=ft.border.all(1, ft.Colors.BLUE_GREY_200),
                    border_radius=8,
                    content=ft.Column(
                        spacing=4,
                        controls=[
                            ft.Text(day, size=12, weight=ft.FontWeight.W_600),
                            *rows,
                        ],
                    ),
                )
            )

    def _map_schedule_status(self, status: str) -> tuple[str, str]:
        if status == "scheduled":
            return "予約済み", ft.Colors.GREEN_600
        if status == "failed":
            return "失敗", ft.Colors.RED_600
        return "予約待ち", ft.Colors.BLUE_GREY_600

    def _on_youtube_action_error(self, message: str) -> None:
        self.youtube_build_button.disabled = False
        self.youtube_execute_button.disabled = False
        # エラー発生時は現状が不明なため、更新で状態同期する。
        self.youtube_reset_failed_button.disabled = False
        self.youtube_refresh_button.disabled = False
        self._append_log(f"YouTube予約エラー: {message}")
        self._toast(f"YouTube予約エラー: {message}")
        self._page.update()

    def _count_failed_items(self, items: list[dict]) -> int:
        return sum(1 for item in items if str(item.get("status") or "").lower() == "failed")

    def _on_error(self, message: str) -> None:
        self.progress_view.set("失敗", 0.0)
        self.start_button.disabled = False
        self.pick_button.disabled = False
        self.resume_output_button.disabled = False
        self.stop_button.disabled = True
        self.submit_button.disabled = False
        self.submit_button.visible = False
        self._toast(f"エラー: {message}")
        self._append_log(f"エラー: {message}")
        self._set_running(False)
        self._page.update()

    def _toast(self, text: str) -> None:
        self.snack.content = ft.Text(text)
        self.snack.open = True
        self._page.update()

    def _on_open_output(self, _: ft.ControlEvent) -> None:
        self._open_output_folder()

    def _open_output_folder(self) -> None:
        if self._last_final_dir is None or not self._last_final_dir.exists():
            self._toast("出力フォルダが見つかりません")
            return

        try:
            subprocess.run(["open", str(self._last_final_dir)], check=True)
            self._append_log(f"出力フォルダを開きました: {self._last_final_dir}")
        except Exception as exc:
            self._toast(f"フォルダを開けませんでした: {exc}")

    def _set_running(self, running: bool) -> None:
        if running:
            now = time.time()
            self._job_running = True
            self._job_started_at = now
            self._last_progress_at = now
            self._start_heartbeat()
            return

        self._job_running = False
        self._stop_heartbeat()
        self.stop_button.disabled = True
        self.runtime_text.value = "稼働状態: 待機"

    def _on_stop(self, _: ft.ControlEvent) -> None:
        if not self._job_running:
            return
        self.stop_button.disabled = True
        self.orchestrator.request_stop()
        self._append_log("停止要求を送信しました")
        self._toast("停止要求を送信しました。現在の処理が中断され次第停止します。")
        self._page.update()

    def _start_heartbeat(self) -> None:
        self._stop_heartbeat()
        self._heartbeat_stop = threading.Event()

        def heartbeat() -> None:
            while not self._heartbeat_stop.wait(1.0):
                self._dispatch_ui(self._refresh_runtime_status)

        self._heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
        self._heartbeat_thread.start()

    def _stop_heartbeat(self) -> None:
        self._heartbeat_stop.set()
        self._heartbeat_thread = None

    def _refresh_runtime_status(self) -> None:
        if not self._job_running:
            return

        now = time.time()
        elapsed = int(now - self._job_started_at)
        since_update = int(now - self._last_progress_at)
        worker_alive = self._worker_thread.is_alive() if self._worker_thread else False

        if worker_alive and since_update < 45:
            state = "実行中"
        elif worker_alive:
            state = "実行中（重い処理継続中）"
        else:
            state = "停止"

        self.runtime_text.value = (
            f"稼働状態: {state} / 経過: {self._format_elapsed(elapsed)} / "
            f"最終更新: {since_update}秒前"
        )
        self._page.update()

    def _append_log(self, line: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        self._log_lines.append(f"[{stamp}] {line}")
        self._log_lines = self._log_lines[-100:]
        self.log_box.value = "\n".join(self._log_lines)
        self._page.update()

    def _format_elapsed(self, total_sec: int) -> str:
        mins = total_sec // 60
        secs = total_sec % 60
        return f"{mins:02d}:{secs:02d}"

    def _dispatch_ui(self, callback, *args) -> None:
        try:
            self._page.run_task(self._run_ui_callback, callback, *args)
        except Exception:
            # Page closed or app shutting down.
            return

    async def _run_ui_callback(self, callback, *args) -> None:
        callback(*args)
