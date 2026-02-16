from __future__ import annotations

import shutil
from pathlib import Path

from podcast_clip_factory.domain.models import ClipCandidate, JobStatus, ReviewDecision, TitleOverlayStyle, Transcript
from podcast_clip_factory.infrastructure.storage.artifact_store import ArtifactStore
from podcast_clip_factory.infrastructure.storage.sqlite_repo import SQLiteJobRepository
from podcast_clip_factory.utils.paths import sanitize_filename


class AppOrchestrator:
    def __init__(self, executor, repo: SQLiteJobRepository, store: ArtifactStore, logger) -> None:
        self.executor = executor
        self.repo = repo
        self.store = store
        self.logger = logger

    def run_pipeline(self, input_video: Path, on_progress=None, on_log=None):
        return self.executor.run(input_video=input_video, on_progress=on_progress, on_log=on_log)

    def preflight(self, input_video: Path | None) -> list[str]:
        errors: list[str] = []
        if input_video is None:
            errors.append("入力動画が未選択です。")
        elif not input_video.exists():
            errors.append(f"入力動画が見つかりません: {input_video}")

        if self.executor.settings.llm.require_cloud and not self.executor.settings.llm.gemini_api_key.strip():
            errors.append("GEMINI_API_KEY が未設定です。`.env` に設定してください。")
        return errors

    def get_review_rows(self, job_id: str) -> list[dict]:
        return self.repo.get_review_rows(job_id)

    def finalize_review(
        self,
        job_id: str,
        decisions: list[ReviewDecision],
        title_style: TitleOverlayStyle | None = None,
        on_log=None,
    ) -> dict:
        self.repo.save_review_decisions(job_id, decisions)

        selected_rows = self.repo.load_selected_final(job_id)
        job = self.repo.get_job(job_id)
        final_dir = self.store.final_dir(job_id)
        exported = []

        if selected_rows:
            transcript_path = self.store.transcript_path(job_id)
            transcript = (
                self.store.load_transcript(transcript_path)
                if transcript_path.exists()
                else Transcript(segments=[], duration_sec=0.0)
            )
            candidates = [
                ClipCandidate(
                    clip_id=str(row["clip_id"]),
                    start_sec=float(row["start_sec"]),
                    end_sec=float(row["end_sec"]),
                    title=str(row["title"]),
                    hook="",
                    reason="review_finalize",
                    score=float(row["score"]),
                )
                for row in selected_rows
            ]

            render_output_dir = self.store.job_dir(job_id) / "final_render"
            render_output_dir.mkdir(parents=True, exist_ok=True)

            if on_log:
                on_log("確定出力レンダリングを開始します")

            def _on_render_event(kind: str, idx: int, total: int, title: str) -> None:
                if not on_log:
                    return
                if kind == "started":
                    on_log(f"確定出力レンダリング開始 {idx}/{total}: {title}")
                elif kind == "completed":
                    on_log(f"確定出力レンダリング完了 {idx}/{total}: {title}")
                elif kind == "failed":
                    on_log(f"確定出力レンダリング失敗 {idx}/{total}: {title}")

            rendered = self.executor.renderer.render(
                input_video=job.input_path,
                output_dir=render_output_dir,
                candidates=candidates,
                transcript=transcript,
                title_style=title_style,
                on_event=_on_render_event,
            )

            for idx, row in enumerate(selected_rows, start=1):
                safe_title = sanitize_filename(row["title"])
                dst = final_dir / f"clip_{idx:02d}_{safe_title}.mp4"
                src = rendered[idx - 1].video_path
                shutil.copy2(src, dst)
                exported.append(
                    {
                        "clip_id": row["clip_id"],
                        "title": row["title"],
                        "start_sec": row["start_sec"],
                        "end_sec": row["end_sec"],
                        "score": row["score"],
                        "final_path": str(dst),
                    }
                )

        payload = {
            "job_id": job_id,
            "selected_count": len(exported),
            "clips": exported,
            "title_style": {
                "font_name": title_style.font_name if title_style else "Hiragino Sans W6",
                "font_size": title_style.font_size if title_style else 56,
                "y": title_style.y if title_style else 58,
                "background": title_style.background if title_style else True,
            },
        }
        self.store.write_json(self.store.final_metadata_path(job_id), payload)
        self.repo.update_status(job_id, JobStatus.COMPLETED)
        self.logger.info("job.completed", job_id=job_id, selected_count=len(exported))
        return payload
