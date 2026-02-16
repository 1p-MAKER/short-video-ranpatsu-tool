from __future__ import annotations

import flet as ft

from podcast_clip_factory.domain.models import ReviewDecision, TitleOverlayStyle


class ReviewView(ft.Column):
    def __init__(self) -> None:
        self._rows: list[dict] = []
        self._controls: list[tuple[str, ft.Checkbox, ft.TextField]] = []
        self.font_size_slider = ft.Slider(min=32, max=96, divisions=64, value=56, label="{value}")
        self.y_slider = ft.Slider(min=0, max=260, divisions=52, value=58, label="{value}")
        self.bg_checkbox = ft.Checkbox(label="文字背景を表示", value=True)
        super().__init__(spacing=12)

    def load_rows(self, rows: list[dict]) -> None:
        self.controls.clear()
        self._rows = rows
        self._controls.clear()

        self.controls.append(ft.Text("最終チェック", size=18, weight=ft.FontWeight.W_600))
        self.controls.append(ft.Text("タイトル入力と見た目調整ができます。", color=ft.Colors.BLUE_GREY_500))
        self.controls.append(
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text("タイトル表示設定（フォント: ゴシック体固定）", weight=ft.FontWeight.W_500),
                        ft.Text("フォント: Hiragino Sans W6", size=12, color=ft.Colors.BLUE_GREY_500),
                        ft.Text("フォントサイズ", size=12),
                        self.font_size_slider,
                        ft.Text("上下位置（Y）", size=12),
                        self.y_slider,
                        self.bg_checkbox,
                    ],
                    spacing=4,
                ),
                padding=10,
                border=ft.border.all(1, ft.Colors.BLUE_GREY_200),
                border_radius=8,
            )
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

    def collect_title_style(self) -> TitleOverlayStyle:
        return TitleOverlayStyle(
            font_name="Hiragino Sans W6",
            font_size=int(self.font_size_slider.value or 56),
            y=int(self.y_slider.value or 58),
            background=bool(self.bg_checkbox.value),
        )
