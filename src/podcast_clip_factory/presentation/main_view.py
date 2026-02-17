from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path

import flet as ft

from podcast_clip_factory.domain.models import ReviewDecision
from podcast_clip_factory.presentation.progress_view import ProgressView
from podcast_clip_factory.presentation.result_view import ResultView
from podcast_clip_factory.presentation.review_view import ReviewView


class MainView(ft.Column):
    def __init__(self, page: ft.Page, orchestrator, logger) -> None:
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
        self._default_media_dir = Path(orchestrator.executor.settings.app.default_media_dir).expanduser()

        self.file_picker = ft.FilePicker()
        self._page.services.append(self.file_picker)

        self.path_text = ft.Text("動画未選択", size=13)
        self.pick_button = ft.ElevatedButton("動画を選択", on_click=self._on_pick_clicked)
        self.start_button = ft.ElevatedButton("自動生成を開始", disabled=True, on_click=self._on_start, visible=False)
        self.stop_button = ft.ElevatedButton("停止", disabled=True, on_click=self._on_stop)

        self.progress_view = ProgressView()
        self.runtime_text = ft.Text("稼働状態: 待機", size=13, color=ft.Colors.BLUE_GREY_700)
        self.estimate_text = ft.Text("目安: 50分動画で約15〜25分", size=12, color=ft.Colors.BLUE_GREY_500)
        self.log_box = ft.TextField(
            label="処理ログ（最新100行）",
            value="",
            read_only=True,
            multiline=True,
            min_lines=8,
            max_lines=12,
        )
        self.review_view = ReviewView()
        self.result_view = ResultView()
        self.open_output_button = ft.OutlinedButton(
            "出力フォルダを開く",
            visible=False,
            on_click=self._on_open_output,
        )

        self.submit_button = ft.ElevatedButton("この内容で確定出力", visible=False, on_click=self._on_submit)
        self.snack = ft.SnackBar(ft.Text(""))
        self._page.overlay.append(self.snack)

        super().__init__(
            controls=[
                ft.Text("ショート動画乱発ツール", size=24, weight=ft.FontWeight.BOLD),
                ft.Text("開始から最終チェック手前まで全自動。最後だけ手動確認。", size=13),
                ft.Row([self.pick_button, self.stop_button], spacing=10),
                self.path_text,
                ft.Divider(),
                self.progress_view,
                self.runtime_text,
                self.estimate_text,
                self.log_box,
                ft.Divider(),
                self.review_view,
                self.submit_button,
                ft.Divider(),
                self.result_view,
                self.open_output_button,
            ],
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
        )

    async def _on_pick_clicked(self, _: ft.ControlEvent) -> None:
        initial_dir = (
            str(self._default_media_dir) if self._default_media_dir.exists() else None
        )
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
        self.stop_button.disabled = False
        self.submit_button.visible = False
        self.review_view.controls.clear()
        self.result_view.summary.value = ""
        self.result_view.path_text.value = ""
        self._last_final_dir = None
        self.open_output_button.visible = False
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
        self.result_view.set_result(payload["selected_count"], str(final_dir))
        self.open_output_button.visible = True
        self.start_button.disabled = False
        self.pick_button.disabled = False
        self.stop_button.disabled = True
        self.submit_button.visible = False
        self.submit_button.disabled = False
        self.progress_view.set("確定出力が完了しました", 1.0)
        self._set_running(False)
        self._toast("確定出力が完了しました")
        self._open_output_folder()
        self._page.update()

    def _on_error(self, message: str) -> None:
        self.progress_view.set("失敗", 0.0)
        self.start_button.disabled = False
        self.pick_button.disabled = False
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
