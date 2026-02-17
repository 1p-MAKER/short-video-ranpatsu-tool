from __future__ import annotations

import flet as ft

from podcast_clip_factory.domain.models import ImpactOverlayStyle, ReviewDecision, TitleOverlayStyle


class ReviewView(ft.Column):
    def __init__(self) -> None:
        self._rows: list[dict] = []
        self._controls: list[tuple[str, ft.Checkbox, ft.TextField, ft.TextField]] = []
        self.font_size_slider = ft.Slider(min=24, max=140, value=56, label="{value}")
        self.y_slider = ft.Slider(min=-5000, max=5000, value=58, label="{value}")
        self.y_value_text = ft.Text("58", size=11, color=ft.Colors.BLUE_GREY_600)
        self.bg_checkbox = ft.Checkbox(label="タイトル背景を表示", value=True)
        self.impact_font_size_slider = ft.Slider(min=20, max=120, value=48, label="{value}")
        self.impact_y_slider = ft.Slider(min=-5000, max=5000, value=1480, label="{value}")
        self.impact_y_value_text = ft.Text("1480", size=11, color=ft.Colors.BLUE_GREY_600)
        self.impact_bg_checkbox = ft.Checkbox(label="一言背景を表示", value=True)
        self.preview_scale = 0.24  # 1080x1920 -> 259x460 preview
        self.preview_width = int(1080 * self.preview_scale)
        self.preview_height = int(1920 * self.preview_scale)
        self.preview_title_text = ft.Text(
            "タイトルプレビュー",
            size=max(10, int(56 * self.preview_scale)),
            color=ft.Colors.WHITE,
            weight=ft.FontWeight.W_700,
            text_align=ft.TextAlign.CENTER,
        )
        self.preview_impact_text = ft.Text(
            "インパクト一言プレビュー",
            size=max(9, int(48 * self.preview_scale)),
            color=ft.Colors.WHITE,
            weight=ft.FontWeight.W_700,
            text_align=ft.TextAlign.CENTER,
        )
        self.preview_title_box = ft.Container(
            left=0,
            right=0,
            top=max(0, int(58 * self.preview_scale)),
            padding=8,
            bgcolor=ft.Colors.with_opacity(0.55, ft.Colors.BLACK),
            content=self.preview_title_text,
        )
        self.preview_impact_box = ft.Container(
            left=0,
            right=0,
            top=max(0, int(1480 * self.preview_scale)),
            padding=8,
            bgcolor=ft.Colors.with_opacity(0.55, ft.Colors.BLACK),
            content=self.preview_impact_text,
        )
        self.preview_stack = ft.Stack(
            controls=[
                ft.Container(
                    width=self.preview_width,
                    height=self.preview_height,
                    bgcolor=ft.Colors.BLUE_GREY_700,
                ),
                ft.Container(
                    left=0,
                    right=0,
                    top=int((self.preview_height - int(608 * self.preview_scale)) / 2),
                    height=int(608 * self.preview_scale),
                    bgcolor=ft.Colors.BLUE_GREY_900,
                ),
                self.preview_title_box,
                self.preview_impact_box,
            ],
            width=self.preview_width,
            height=self.preview_height,
        )
        self.font_size_slider.on_change = self._on_style_change
        self.y_slider.on_change = self._on_style_change
        self.y_slider.width = 170
        self.y_slider.rotate = ft.Rotate(angle=-1.5708)
        self.bg_checkbox.on_change = self._on_style_change
        self.impact_font_size_slider.on_change = self._on_style_change
        self.impact_y_slider.on_change = self._on_style_change
        self.impact_y_slider.width = 170
        self.impact_y_slider.rotate = ft.Rotate(angle=-1.5708)
        self.impact_bg_checkbox.on_change = self._on_style_change
        super().__init__(spacing=12)

    def load_rows(self, rows: list[dict]) -> None:
        self.controls.clear()
        self._rows = rows
        self._controls.clear()

        self.controls.append(ft.Text("最終チェック", size=18, weight=ft.FontWeight.W_600))
        self.controls.append(ft.Text("タイトル入力と見た目調整", color=ft.Colors.BLUE_GREY_500, size=12))
        self.controls.append(
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Container(
                            width=360,
                            content=ft.Column(
                                [
                                    ft.Text("タイトル設定", weight=ft.FontWeight.W_500),
                                    ft.Text("サイズ", size=11),
                                    self.font_size_slider,
                                    ft.Row(
                                        controls=[
                                            ft.Text("Y", size=11),
                                            ft.Container(width=44, height=170, content=self.y_slider),
                                            self.y_value_text,
                                            self.bg_checkbox,
                                        ],
                                        spacing=8,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                    ft.Divider(height=8),
                                    ft.Text("下段一言設定", weight=ft.FontWeight.W_500),
                                    ft.Text("サイズ", size=11),
                                    self.impact_font_size_slider,
                                    ft.Row(
                                        controls=[
                                            ft.Text("Y", size=11),
                                            ft.Container(width=44, height=170, content=self.impact_y_slider),
                                            self.impact_y_value_text,
                                            self.impact_bg_checkbox,
                                        ],
                                        spacing=8,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                ],
                                spacing=4,
                                tight=True,
                            ),
                        ),
                        ft.Container(
                            content=ft.Column(
                                controls=[
                                    ft.Text("簡易プレビュー", size=12),
                                    ft.Container(
                                        content=self.preview_stack,
                                        border=ft.border.all(1, ft.Colors.BLUE_GREY_300),
                                        border_radius=6,
                                    ),
                                ],
                                spacing=4,
                            ),
                        ),
                    ],
                    spacing=14,
                    wrap=True,
                    vertical_alignment=ft.CrossAxisAlignment.START,
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
                on_change=self._on_title_change,
            )
            impact = ft.TextField(
                label="インパクト一言（下段表示）",
                value=(row.get("hook") or "").strip()[:40],
                max_length=40,
                width=500,
                on_change=self._on_impact_change,
            )
            meta = ft.Text(
                f"{row['start_sec']:.1f}s - {row['end_sec']:.1f}s / score={row['score']:.2f}",
                size=12,
                color=ft.Colors.BLUE_GREY_500,
            )
            card = ft.Container(
                content=ft.Column([selected, title, impact, meta], spacing=6),
                padding=10,
                border=ft.border.all(1, ft.Colors.BLUE_GREY_200),
                border_radius=8,
            )
            self.controls.append(card)
            self._controls.append((row["clip_id"], selected, title, impact))
        if self._controls:
            self.preview_title_text.value = (self._controls[0][2].value or "").strip()[:28] or "タイトルプレビュー"
            self.preview_impact_text.value = (
                (self._controls[0][3].value or "").strip()[:40] or "インパクト一言プレビュー"
            )
            self._sync_preview()

    def collect_decisions(self) -> list[ReviewDecision]:
        decisions: list[ReviewDecision] = []
        for clip_id, selected, title, _impact in self._controls:
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

    def collect_impact_style(self) -> ImpactOverlayStyle:
        return ImpactOverlayStyle(
            font_name="Hiragino Sans W6",
            font_size=int(self.impact_font_size_slider.value or 48),
            y=int(self.impact_y_slider.value or 1480),
            background=bool(self.impact_bg_checkbox.value),
        )

    def collect_impact_phrases(self) -> dict[str, str]:
        return {
            clip_id: (impact.value or "").strip()[:40]
            for clip_id, _selected, _title, impact in self._controls
        }

    def _on_title_change(self, e: ft.ControlEvent) -> None:
        value = (e.control.value or "").strip()[:28]
        self.preview_title_text.value = value or "タイトルプレビュー"
        self._sync_preview()

    def _on_impact_change(self, e: ft.ControlEvent) -> None:
        value = (e.control.value or "").strip()[:40]
        self.preview_impact_text.value = value or "インパクト一言プレビュー"
        self._sync_preview()

    def _on_style_change(self, _: ft.ControlEvent) -> None:
        self._sync_preview()

    def _sync_preview(self) -> None:
        font_size = int(self.font_size_slider.value or 56)
        y = int(self.y_slider.value or 58)
        background = bool(self.bg_checkbox.value)
        impact_font_size = int(self.impact_font_size_slider.value or 48)
        impact_y = int(self.impact_y_slider.value or 1480)
        impact_background = bool(self.impact_bg_checkbox.value)
        self.y_value_text.value = str(y)
        self.impact_y_value_text.value = str(impact_y)

        self.preview_title_text.size = max(10, int(font_size * self.preview_scale))
        self.preview_title_box.top = int(y * self.preview_scale)
        self.preview_title_box.bgcolor = (
            ft.Colors.with_opacity(0.55, ft.Colors.BLACK) if background else None
        )
        self.preview_title_box.padding = 8 if background else 0

        self.preview_impact_text.size = max(9, int(impact_font_size * self.preview_scale))
        self.preview_impact_box.top = int(impact_y * self.preview_scale)
        self.preview_impact_box.bgcolor = (
            ft.Colors.with_opacity(0.55, ft.Colors.BLACK) if impact_background else None
        )
        self.preview_impact_box.padding = 8 if impact_background else 0
        try:
            self.preview_stack.update()
            self.y_value_text.update()
            self.impact_y_value_text.update()
        except Exception:
            return
