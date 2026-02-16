from __future__ import annotations

import flet as ft


class ResultView(ft.Column):
    def __init__(self) -> None:
        self.summary = ft.Text("")
        self.path_text = ft.Text("")
        super().__init__(controls=[self.summary, self.path_text], spacing=4)

    def set_result(self, selected_count: int, final_dir: str) -> None:
        self.summary.value = f"確定出力が完了しました。採用本数: {selected_count}"
        self.path_text.value = f"出力先: {final_dir}"
