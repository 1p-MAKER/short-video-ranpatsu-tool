from __future__ import annotations

import shutil
from pathlib import Path

from podcast_clip_factory.domain.models import JobStatus, ReviewDecision
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

    def get_review_rows(self, job_id: str) -> list[dict]:
        return self.repo.get_review_rows(job_id)

    def finalize_review(self, job_id: str, decisions: list[ReviewDecision]) -> dict:
        self.repo.save_review_decisions(job_id, decisions)

        selected_rows = self.repo.load_selected_final(job_id)
        final_dir = self.store.final_dir(job_id)
        exported = []

        for idx, row in enumerate(selected_rows, start=1):
            src = Path(row["video_path"])
            safe_title = sanitize_filename(row["title"])
            dst = final_dir / f"clip_{idx:02d}_{safe_title}.mp4"
            if src.exists():
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
        }
        self.store.write_json(self.store.final_metadata_path(job_id), payload)
        self.repo.update_status(job_id, JobStatus.COMPLETED)
        self.logger.info("job.completed", job_id=job_id, selected_count=len(exported))
        return payload
