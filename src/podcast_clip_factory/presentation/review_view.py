from __future__ import annotations

import flet as ft

from podcast_clip_factory.domain.models import ReviewDecision


class ReviewView(ft.Column):
    def __init__(self) -> None:
        self._rows: list[dict] = []
        self._controls: list[tuple[str, ft.Checkbox, ft.TextField]] = []
        super().__init__(spacing=12)

    def load_rows(self, rows: list[dict]) -> None:
        self.controls.clear()
        self._rows = rows
        self._controls.clear()

        self.controls.append(ft.Text("最終チェック", size=18, weight=ft.FontWeight.W_600))
        self.controls.append(
            ft.Text("採用/除外 と タイトル編集のみ可能です。", color=ft.Colors.BLUE_GREY_500)
        )

        for row in rows:
            selected = ft.Checkbox(label=f"採用 ({row['clip_id']})", value=bool(row["selected"]))
            title = ft.TextField(
                label="タイトル",
                value=row.get("edited_title") or row["title"],
                max_length=28,
                width=500,
            )
            meta = ft.Text(
                f"{row['start_sec']:.1f}s - {row['end_sec']:.1f}s / score={row['score']:.2f}",
                size=12,
                color=ft.Colors.BLUE_GREY_500,
            )
            card = ft.Container(
                content=ft.Column([selected, title, meta], spacing=6),
                padding=10,
                border=ft.border.all(1, ft.Colors.BLUE_GREY_200),
                border_radius=8,
            )
            self.controls.append(card)
            self._controls.append((row["clip_id"], selected, title))

    def collect_decisions(self) -> list[ReviewDecision]:
        decisions: list[ReviewDecision] = []
        for clip_id, selected, title in self._controls:
            decisions.append(
                ReviewDecision(
                    clip_id=clip_id,
                    selected=bool(selected.value),
                    edited_title=(title.value or "").strip()[:28],
                )
            )
        return decisions
