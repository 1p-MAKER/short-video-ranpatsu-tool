from __future__ import annotations

import threading
from pathlib import Path

import flet as ft

from podcast_clip_factory.domain.models import ReviewDecision
from podcast_clip_factory.presentation.progress_view import ProgressView
from podcast_clip_factory.presentation.result_view import ResultView
from podcast_clip_factory.presentation.review_view import ReviewView


class MainView(ft.Column):
    def __init__(self, page: ft.Page, orchestrator, logger) -> None:
        self.page = page
        self.orchestrator = orchestrator
        self.logger = logger

        self.selected_video: Path | None = None
        self.current_job_id: str | None = None

        self.file_picker = ft.FilePicker(on_result=self._on_pick_result)
        self.page.overlay.append(self.file_picker)

        self.path_text = ft.Text("動画未選択", size=13)
        self.pick_button = ft.ElevatedButton("動画を選択", on_click=self._on_pick_clicked)
        self.start_button = ft.ElevatedButton("自動生成を開始", disabled=True, on_click=self._on_start)

        self.progress_view = ProgressView()
        self.review_view = ReviewView()
        self.result_view = ResultView()

        self.submit_button = ft.ElevatedButton("この内容で確定出力", visible=False, on_click=self._on_submit)
        self.snack = ft.SnackBar(ft.Text(""))
        self.page.overlay.append(self.snack)

        super().__init__(
            controls=[
                ft.Text("ポッドキャスト切り抜き自動化ファクトリー", size=24, weight=ft.FontWeight.BOLD),
                ft.Text("開始から最終チェック手前まで全自動。最後だけ手動確認。", size=13),
                ft.Row([self.pick_button, self.start_button], spacing=10),
                self.path_text,
                ft.Divider(),
                self.progress_view,
                ft.Divider(),
                self.review_view,
                self.submit_button,
                ft.Divider(),
                self.result_view,
            ],
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
        )

    def _on_pick_clicked(self, _: ft.ControlEvent) -> None:
        self.file_picker.pick_files(allow_multiple=False)

    def _on_pick_result(self, e: ft.FilePickerResultEvent) -> None:
        if not e.files:
            return
        self.selected_video = Path(e.files[0].path)
        self.path_text.value = f"選択中: {self.selected_video}"
        self.start_button.disabled = False
        self.page.update()

    def _on_start(self, _: ft.ControlEvent) -> None:
        if self.selected_video is None:
            self._toast("動画を選択してください")
            return

        self.start_button.disabled = True
        self.pick_button.disabled = True
        self.submit_button.visible = False
        self.review_view.controls.clear()
        self.result_view.summary.value = ""
        self.result_view.path_text.value = ""
        self.progress_view.set("ジョブ開始", 0.01)
        self.page.update()

        def worker() -> None:
            try:
                result = self.orchestrator.run_pipeline(
                    self.selected_video,
                    on_progress=lambda msg, p: self.page.call_from_thread(
                        self._update_progress, msg, p
                    ),
                )
                rows = self.orchestrator.get_review_rows(result.job.job_id)
                self.current_job_id = result.job.job_id
                self.page.call_from_thread(self._show_review_rows, rows)
            except Exception as exc:
                self.logger.exception("ui.pipeline_failed", error=str(exc))
                self.page.call_from_thread(self._on_error, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _update_progress(self, message: str, value: float) -> None:
        self.progress_view.set(message, value)
        self.page.update()

    def _show_review_rows(self, rows: list[dict]) -> None:
        self.review_view.load_rows(rows)
        self.submit_button.visible = True
        self.progress_view.set("最終チェックで採用可否・タイトルを確認してください", 1.0)
        self.page.update()

    def _on_submit(self, _: ft.ControlEvent) -> None:
        if not self.current_job_id:
            self._toast("ジョブが存在しません")
            return

        decisions: list[ReviewDecision] = self.review_view.collect_decisions()
        payload = self.orchestrator.finalize_review(self.current_job_id, decisions)
        final_dir = self.orchestrator.store.final_dir(self.current_job_id)
        self.result_view.set_result(payload["selected_count"], str(final_dir))
        self.start_button.disabled = False
        self.pick_button.disabled = False
        self.submit_button.visible = False
        self._toast("確定出力が完了しました")
        self.page.update()

    def _on_error(self, message: str) -> None:
        self.progress_view.set("失敗", 0.0)
        self.start_button.disabled = False
        self.pick_button.disabled = False
        self.submit_button.visible = False
        self._toast(f"エラー: {message}")
        self.page.update()

    def _toast(self, text: str) -> None:
        self.snack.content = ft.Text(text)
        self.snack.open = True
        self.page.update()
