"""クラウド登録 GUI アプリ (Flet)"""
from __future__ import annotations

import os
import threading
from datetime import datetime
from pathlib import Path

import flet as ft

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*_a, **_kw):
        return False


ROOT_DIR = Path(__file__).resolve().parents[2]


# ── テーマカラー ──────────────────────────────────
PRIMARY = "#6C63FF"
PRIMARY_DARK = "#5A52E0"
SURFACE = "#1E1E2E"
SURFACE_DIM = "#181825"
CARD_BG = "#2A2A3C"
TEXT_PRIMARY = "#E0E0F0"
TEXT_SECONDARY = "#A0A0C0"
SUCCESS = "#4ADE80"
ERROR = "#F87171"
WARNING = "#FBBF24"


def _count_mp4(job_dir: Path) -> int:
    return sum(1 for _ in job_dir.rglob("*.mp4"))


def _job_mtime(job_dir: Path) -> float:
    return job_dir.stat().st_mtime


class JobCard(ft.Container):
    """ジョブ1件を表すカード"""

    def __init__(self, job_id: str, mp4_count: int, mod_date: str, selected: bool, on_tap):
        self.job_id = job_id
        self._selected = selected

        self._title = ft.Text(
            job_id,
            size=15,
            weight=ft.FontWeight.W_600,
            color=TEXT_PRIMARY,
            font_family="Roboto Mono",
        )
        self._subtitle = ft.Text(
            f"🎬 {mp4_count}本  ·  📅 {mod_date}",
            size=13,
            color=TEXT_SECONDARY,
        )
        self._check = ft.Icon(
            ft.Icons.CHECK_CIRCLE_ROUNDED if selected else ft.Icons.RADIO_BUTTON_UNCHECKED,
            color=PRIMARY if selected else TEXT_SECONDARY,
            size=24,
        )

        super().__init__(
            content=ft.Row(
                [
                    ft.Column([self._title, self._subtitle], spacing=2, expand=True),
                    self._check,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=16, vertical=14),
            border_radius=12,
            bgcolor=CARD_BG,
            border=ft.border.all(2, PRIMARY) if selected else ft.border.all(1, "#3A3A4C"),
            on_click=on_tap,
            animate=ft.animation.Animation(200, ft.AnimationCurve.EASE_IN_OUT),
            ink=True,
        )

    def set_selected(self, selected: bool):
        self._selected = selected
        self._check.name = ft.Icons.CHECK_CIRCLE_ROUNDED if selected else ft.Icons.RADIO_BUTTON_UNCHECKED
        self._check.color = PRIMARY if selected else TEXT_SECONDARY
        self.border = ft.border.all(2, PRIMARY) if selected else ft.border.all(1, "#3A3A4C")


class CloudDeployApp(ft.Column):
    """メインアプリケーション"""

    def __init__(self, page: ft.Page):
        super().__init__(expand=True, spacing=0)
        self._page = page
        self._selected_job: str | None = None
        self._cards: dict[str, JobCard] = {}
        self._is_running = False

        # ── UI部品 ──
        self._header = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.CLOUD_UPLOAD_ROUNDED, color=PRIMARY, size=32),
                    ft.Column(
                        [
                            ft.Text("Cloud Deploy", size=24, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
                            ft.Text("動画をクラウドに登録して自動配信", size=13, color=TEXT_SECONDARY),
                        ],
                        spacing=2,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.only(left=24, right=24, top=20, bottom=16),
        )

        self._job_list = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)

        self._status_text = ft.Text("ジョブを選択してください", size=13, color=TEXT_SECONDARY)
        self._progress = ft.ProgressBar(visible=False, color=PRIMARY, bgcolor="#3A3A4C")

        self._log_box = ft.TextField(
            multiline=True,
            read_only=True,
            min_lines=6,
            max_lines=6,
            text_size=12,
            color=TEXT_SECONDARY,
            bgcolor=SURFACE_DIM,
            border_color="#3A3A4C",
            border_radius=8,
            visible=False,
            text_style=ft.TextStyle(font_family="Roboto Mono"),
        )

        self._deploy_btn = ft.ElevatedButton(
            text="☁️  クラウドに登録",
            bgcolor=PRIMARY,
            color="white",
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=12),
                padding=ft.padding.symmetric(horizontal=32, vertical=16),
                text_style=ft.TextStyle(size=16, weight=ft.FontWeight.W_600),
            ),
            on_click=self._on_deploy,
            disabled=True,
            height=52,
            expand=True,
        )

        self._refresh_btn = ft.IconButton(
            icon=ft.Icons.REFRESH_ROUNDED,
            icon_color=TEXT_SECONDARY,
            tooltip="一覧を更新",
            on_click=self._on_refresh,
        )

        # ── レイアウト組み立て ──
        self.controls = [
            self._header,
            ft.Divider(height=1, color="#3A3A4C"),
            # ジョブ一覧ヘッダ
            ft.Container(
                content=ft.Row(
                    [
                        ft.Text("📂 ジョブ一覧", size=14, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
                        self._refresh_btn,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                padding=ft.padding.only(left=24, right=16, top=12),
            ),
            # ジョブリスト
            ft.Container(
                content=self._job_list,
                padding=ft.padding.symmetric(horizontal=24),
                expand=True,
            ),
            # ステータスエリア
            ft.Container(
                content=ft.Column(
                    [
                        self._progress,
                        self._status_text,
                        self._log_box,
                    ],
                    spacing=8,
                ),
                padding=ft.padding.symmetric(horizontal=24, vertical=8),
            ),
            # デプロイボタン
            ft.Container(
                content=ft.Row([self._deploy_btn]),
                padding=ft.padding.only(left=24, right=24, bottom=20, top=8),
            ),
        ]

        self._load_jobs()

    # ── ジョブ読み込み ────────────────────────
    def _load_jobs(self):
        runs_dir = ROOT_DIR / "runs"
        job_dirs = [
            d for d in runs_dir.iterdir()
            if d.is_dir() and d.name != "zzztest" and not d.name.startswith(".")
        ]
        job_dirs.sort(key=_job_mtime, reverse=True)

        self._job_list.controls.clear()
        self._cards.clear()

        if not job_dirs:
            self._job_list.controls.append(
                ft.Container(
                    content=ft.Text("ジョブが見つかりません", color=TEXT_SECONDARY, size=14),
                    padding=20,
                    alignment=ft.alignment.center,
                )
            )
        else:
            for d in job_dirs:
                job_id = d.name
                mp4_count = _count_mp4(d)
                mod_date = datetime.fromtimestamp(d.stat().st_mtime).strftime("%m/%d %H:%M")
                card = JobCard(
                    job_id=job_id,
                    mp4_count=mp4_count,
                    mod_date=mod_date,
                    selected=(job_id == self._selected_job),
                    on_tap=lambda e, jid=job_id: self._on_select(jid),
                )
                self._cards[job_id] = card
                self._job_list.controls.append(card)

        self._page.update()

    def _on_select(self, job_id: str):
        if self._is_running:
            return
        self._selected_job = job_id
        for jid, card in self._cards.items():
            card.set_selected(jid == job_id)
        self._deploy_btn.disabled = False
        self._status_text.value = f"✅ 選択中: {job_id}"
        self._status_text.color = TEXT_PRIMARY
        self._page.update()

    def _on_refresh(self, _e):
        if self._is_running:
            return
        self._load_jobs()

    # ── デプロイ実行 ──────────────────────────
    def _on_deploy(self, _e):
        if not self._selected_job or self._is_running:
            return

        self._is_running = True
        self._deploy_btn.disabled = True
        self._deploy_btn.text = "⏳ アップロード中..."
        self._deploy_btn.bgcolor = PRIMARY_DARK
        self._progress.visible = True
        self._log_box.visible = True
        self._log_box.value = ""
        self._status_text.value = "🚀 クラウドに登録中..."
        self._status_text.color = WARNING
        self._page.update()

        threading.Thread(target=self._run_deploy, daemon=True).start()

    def _run_deploy(self):
        job_id = self._selected_job
        try:
            self._log(f"ジョブ: {job_id}")
            self._log("ローカルデータを読み込み中...")

            from podcast_clip_factory.app import build_orchestrator
            from podcast_clip_factory.infrastructure.cloud.firestore_repo import FirestoreJobRepository
            from podcast_clip_factory.infrastructure.cloud.gcs_uploader import GCSUploader

            local_orch = build_orchestrator(ROOT_DIR)
            items = local_orch.repo.list_youtube_schedule(job_id)

            if not items:
                self._log("⚠️ アップロード対象のアイテムがありません。")
                self._finish(success=False, message="アイテムが見つかりませんでした")
                return

            self._log(f"対象: {len(items)}件")

            uploader = GCSUploader()
            firestore_repo = FirestoreJobRepository()

            uploaded = []
            for i, item in enumerate(items):
                local_path = item.video_path
                if not local_path.exists():
                    self._log(f"⚠️ スキップ: {local_path.name} (ファイルなし)")
                    continue

                blob_name = f"videos/{job_id}/{local_path.name}"
                self._log(f"[{i+1}/{len(items)}] {local_path.name}")
                gs_uri = uploader.upload_file(local_path, blob_name)
                item.video_path = Path(gs_uri)
                uploaded.append(item)

            if not uploaded:
                self._finish(success=False, message="有効なファイルがありませんでした")
                return

            self._log(f"Firestoreへ {len(uploaded)}件 登録中...")
            firestore_repo.replace_youtube_schedule(job_id, uploaded)
            self._log("✅ 完了！")
            self._finish(success=True, message=f"{len(uploaded)}件をクラウドに登録しました！")

        except Exception as exc:
            self._log(f"❌ エラー: {exc}")
            self._finish(success=False, message=f"エラー: {str(exc)[:100]}")

    def _log(self, msg: str):
        current = self._log_box.value or ""
        self._log_box.value = current + msg + "\n" if current else msg + "\n"
        self._page.update()

    def _finish(self, *, success: bool, message: str):
        self._is_running = False
        self._progress.visible = False
        self._deploy_btn.disabled = False
        self._deploy_btn.text = "☁️  クラウドに登録"
        self._deploy_btn.bgcolor = PRIMARY

        if success:
            self._status_text.value = f"🎉 {message}"
            self._status_text.color = SUCCESS
        else:
            self._status_text.value = f"⚠️ {message}"
            self._status_text.color = ERROR

        self._page.update()


def main():
    load_dotenv(ROOT_DIR / ".env", override=True)

    def _run(page: ft.Page):
        page.title = "Cloud Deploy"
        page.window.width = 480
        page.window.height = 680
        page.window.min_width = 400
        page.window.min_height = 600
        page.bgcolor = SURFACE
        page.padding = 0
        page.fonts = {"Roboto Mono": "https://fonts.googleapis.com/css2?family=Roboto+Mono&display=swap"}

        app = CloudDeployApp(page)
        page.add(app)

    ft.run(_run)


if __name__ == "__main__":
    main()
