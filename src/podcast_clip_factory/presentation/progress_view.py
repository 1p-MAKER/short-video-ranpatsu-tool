from __future__ import annotations

import flet as ft


class ProgressView(ft.Column):
    def __init__(self) -> None:
        self.status_text = ft.Text("待機中", size=14)
        self.progress = ft.ProgressBar(width=700, value=0)
        super().__init__(controls=[self.status_text, self.progress], spacing=8)

    def set(self, message: str, value: float) -> None:
        self.status_text.value = message
        self.progress.value = max(0.0, min(1.0, value))
