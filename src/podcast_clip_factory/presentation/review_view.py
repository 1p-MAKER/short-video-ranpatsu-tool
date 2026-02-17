from __future__ import annotations

import flet as ft

from podcast_clip_factory.domain.models import ImpactOverlayStyle, ReviewDecision, TitleOverlayStyle


class ReviewView(ft.Column):
    def __init__(self) -> None:
        self.canvas_width = 1080
        self.canvas_height = 1920
        self.center_height = 608
        self.center_top = int((self.canvas_height - self.center_height) / 2)  # 656
        self.center_bottom = self.center_top + self.center_height  # 1264
        self.safe_margin = 24

        self._rows: list[dict] = []
        self._controls: list[tuple[str, ft.Checkbox, ft.TextField, ft.TextField]] = []
        self.font_size_slider = ft.Slider(min=24, max=140, value=56, divisions=116, label="{value}")
        self.y_min = 24
        self.y_max = 608
        self.y_value = 96
        self.y_value_text = ft.Text("96", size=11, color=ft.Colors.BLUE_GREY_600)
        self.bg_checkbox = ft.Checkbox(label="タイトル背景を表示", value=True)
        self.impact_font_size_slider = ft.Slider(min=20, max=120, value=48, divisions=100, label="{value}")
        self.impact_y_min = 1288
        self.impact_y_max = 1876
        self.impact_y_value = 1520
        self.impact_y_value_text = ft.Text("1520", size=11, color=ft.Colors.BLUE_GREY_600)
        self.impact_bg_checkbox = ft.Checkbox(label="一言背景を表示", value=True)
        self.y_track_height = 320
        self.y_thumb_size = 22
        self.y_track_line = ft.Container(
            width=6,
            height=self.y_track_height,
            bgcolor=ft.Colors.BLUE_GREY_200,
            border_radius=3,
            left=19,
            top=0,
        )
        self.y_thumb = ft.Container(
            width=self.y_thumb_size,
            height=self.y_thumb_size,
            bgcolor=ft.Colors.BLUE_500,
            border_radius=11,
            left=11,
            top=0,
        )
        self.y_track_stack = ft.Stack(
            controls=[self.y_track_line, self.y_thumb],
            width=44,
            height=self.y_track_height,
        )
        self.y_track_gesture = ft.GestureDetector(
            content=self.y_track_stack,
            on_pan_update=self._on_y_pan,
            on_tap_down=self._on_y_tap,
        )
        self.impact_track_line = ft.Container(
            width=6,
            height=self.y_track_height,
            bgcolor=ft.Colors.BLUE_GREY_200,
            border_radius=3,
            left=19,
            top=0,
        )
        self.impact_thumb = ft.Container(
            width=self.y_thumb_size,
            height=self.y_thumb_size,
            bgcolor=ft.Colors.BLUE_500,
            border_radius=11,
            left=11,
            top=0,
        )
        self.impact_track_stack = ft.Stack(
            controls=[self.impact_track_line, self.impact_thumb],
            width=44,
            height=self.y_track_height,
        )
        self.impact_track_gesture = ft.GestureDetector(
            content=self.impact_track_stack,
            on_pan_update=self._on_impact_pan,
            on_tap_down=self._on_impact_tap,
        )
        self.preview_scale = 0.24  # 1080x1920 -> 259x460 preview
        self.preview_width = int(self.canvas_width * self.preview_scale)
        self.preview_height = int(self.canvas_height * self.preview_scale)
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
            max_lines=3,
            width=self.preview_width - 20,
        )
        self.preview_title_box = ft.Container(
            left=0,
            right=0,
            top=max(0, int(96 * self.preview_scale)),
            padding=8,
            bgcolor=ft.Colors.with_opacity(0.55, ft.Colors.BLACK),
            content=self.preview_title_text,
        )
        self.preview_impact_box = ft.Container(
            left=0,
            right=0,
            top=max(0, int(1520 * self.preview_scale)),
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
                    top=int((self.preview_height - int(self.center_height * self.preview_scale)) / 2),
                    height=int(self.center_height * self.preview_scale),
                    bgcolor=ft.Colors.BLUE_GREY_900,
                ),
                self.preview_title_box,
                self.preview_impact_box,
            ],
            width=self.preview_width,
            height=self.preview_height,
        )
        self.font_size_slider.on_change = self._on_style_change
        self.bg_checkbox.on_change = self._on_style_change
        self.impact_font_size_slider.on_change = self._on_style_change
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
                                            ft.Column(
                                                controls=[
                                                    ft.IconButton(
                                                        icon=ft.Icons.KEYBOARD_ARROW_UP,
                                                        icon_size=18,
                                                        on_click=lambda _e: self._nudge_y(-2),
                                                    ),
                                                    self.y_track_gesture,
                                                    ft.IconButton(
                                                        icon=ft.Icons.KEYBOARD_ARROW_DOWN,
                                                        icon_size=18,
                                                        on_click=lambda _e: self._nudge_y(2),
                                                    ),
                                                ],
                                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                                spacing=2,
                                            ),
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
                                            ft.Column(
                                                controls=[
                                                    ft.IconButton(
                                                        icon=ft.Icons.KEYBOARD_ARROW_UP,
                                                        icon_size=18,
                                                        on_click=lambda _e: self._nudge_impact_y(-2),
                                                    ),
                                                    self.impact_track_gesture,
                                                    ft.IconButton(
                                                        icon=ft.Icons.KEYBOARD_ARROW_DOWN,
                                                        icon_size=18,
                                                        on_click=lambda _e: self._nudge_impact_y(2),
                                                    ),
                                                ],
                                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                                spacing=2,
                                            ),
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
        font_size = int(self.font_size_slider.value or 56)
        return TitleOverlayStyle(
            font_name="Hiragino Sans W6",
            font_size=font_size,
            y=self._clamp_title_y(int(self.y_value), font_size),
            background=bool(self.bg_checkbox.value),
        )

    def collect_impact_style(self) -> ImpactOverlayStyle:
        font_size = int(self.impact_font_size_slider.value or 48)
        return ImpactOverlayStyle(
            font_name="Hiragino Sans W6",
            font_size=font_size,
            y=self._clamp_impact_y(int(self.impact_y_value), font_size),
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
        y = self._clamp_title_y(int(self.y_value), font_size)
        background = bool(self.bg_checkbox.value)
        impact_font_size = int(self.impact_font_size_slider.value or 48)
        impact_y = self._clamp_impact_y(int(self.impact_y_value), impact_font_size)
        impact_background = bool(self.impact_bg_checkbox.value)
        self.y_value = y
        self.impact_y_value = impact_y
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
        self.y_thumb.top = self._value_to_thumb_top(y, self.y_min, self.y_max)
        self.impact_thumb.top = self._value_to_thumb_top(
            impact_y, self.impact_y_min, self.impact_y_max
        )
        try:
            self.preview_stack.update()
            self.y_track_stack.update()
            self.impact_track_stack.update()
            self.y_value_text.update()
            self.impact_y_value_text.update()
        except Exception:
            return

    def _clamp_title_y(self, y: int, font_size: int) -> int:
        min_y = self.safe_margin
        max_y = max(min_y, self.center_top - font_size - self.safe_margin)
        return max(min_y, min(max_y, y))

    def _clamp_impact_y(self, y: int, font_size: int) -> int:
        min_y = self.center_bottom + self.safe_margin
        max_y = max(min_y, self.canvas_height - font_size - self.safe_margin)
        return max(min_y, min(max_y, y))

    def _nudge_y(self, delta: int) -> None:
        self.y_value = max(self.y_min, min(self.y_max, int(self.y_value + delta)))
        self._sync_preview()

    def _nudge_impact_y(self, delta: int) -> None:
        self.impact_y_value = max(
            self.impact_y_min, min(self.impact_y_max, int(self.impact_y_value + delta))
        )
        self._sync_preview()

    def _on_y_pan(self, e: ft.DragUpdateEvent) -> None:
        delta = getattr(e, "delta_y", 0.0) or 0.0
        self._apply_y_drag(delta)

    def _on_impact_pan(self, e: ft.DragUpdateEvent) -> None:
        delta = getattr(e, "delta_y", 0.0) or 0.0
        self._apply_impact_drag(delta)

    def _on_y_tap(self, e: ft.TapEvent) -> None:
        y = getattr(e, "local_y", None)
        if y is None:
            return
        self.y_value = self._thumb_top_to_value(float(y) - self.y_thumb_size / 2, self.y_min, self.y_max)
        self._sync_preview()

    def _on_impact_tap(self, e: ft.TapEvent) -> None:
        y = getattr(e, "local_y", None)
        if y is None:
            return
        self.impact_y_value = self._thumb_top_to_value(
            float(y) - self.y_thumb_size / 2, self.impact_y_min, self.impact_y_max
        )
        self._sync_preview()

    def _apply_y_drag(self, delta_y: float) -> None:
        rng = self.y_max - self.y_min
        if rng <= 0:
            return
        px_range = max(1.0, float(self.y_track_height - self.y_thumb_size))
        step = rng / px_range
        self.y_value = max(self.y_min, min(self.y_max, int(round(self.y_value + delta_y * step))))
        self._sync_preview()

    def _apply_impact_drag(self, delta_y: float) -> None:
        rng = self.impact_y_max - self.impact_y_min
        if rng <= 0:
            return
        px_range = max(1.0, float(self.y_track_height - self.y_thumb_size))
        step = rng / px_range
        self.impact_y_value = max(
            self.impact_y_min,
            min(self.impact_y_max, int(round(self.impact_y_value + delta_y * step))),
        )
        self._sync_preview()

    def _value_to_thumb_top(self, value: int, min_value: int, max_value: int) -> float:
        rng = max(1, max_value - min_value)
        ratio = (value - min_value) / rng
        px_range = max(1.0, float(self.y_track_height - self.y_thumb_size))
        return max(0.0, min(px_range, ratio * px_range))

    def _thumb_top_to_value(self, top: float, min_value: int, max_value: int) -> int:
        px_range = max(1.0, float(self.y_track_height - self.y_thumb_size))
        clamped_top = max(0.0, min(px_range, top))
        ratio = clamped_top / px_range
        return int(round(min_value + ratio * (max_value - min_value)))
