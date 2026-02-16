from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from podcast_clip_factory.domain.models import ClipCandidate, JobRecord, JobStatus, RenderedClip, ReviewDecision


class SQLiteJobRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    input_path TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error_message TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS clips (
                    job_id TEXT NOT NULL,
                    clip_id TEXT NOT NULL,
                    start_sec REAL NOT NULL,
                    end_sec REAL NOT NULL,
                    title TEXT NOT NULL,
                    hook TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    score REAL NOT NULL,
                    video_path TEXT NOT NULL DEFAULT '',
                    subtitle_path TEXT NOT NULL DEFAULT '',
                    selected INTEGER NOT NULL DEFAULT 1,
                    edited_title TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (job_id, clip_id)
                );
                """
            )

    def create_job(self, input_path: Path) -> JobRecord:
        now = datetime.now(timezone.utc).isoformat()
        job_id = uuid4().hex[:12]
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (job_id, input_path, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (job_id, str(input_path), JobStatus.QUEUED.value, now, now),
            )

        return JobRecord(job_id=job_id, input_path=input_path, status=JobStatus.QUEUED)

    def update_status(self, job_id: str, status: JobStatus, error_message: str = "") -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, error_message = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (status.value, error_message, now, job_id),
            )

    def get_job(self, job_id: str) -> JobRecord:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT job_id, input_path, status, created_at, updated_at, error_message FROM jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()

        if not row:
            raise KeyError(f"Job not found: {job_id}")

        return JobRecord(
            job_id=row[0],
            input_path=Path(row[1]),
            status=JobStatus(row[2]),
            created_at=datetime.fromisoformat(row[3]),
            updated_at=datetime.fromisoformat(row[4]),
            error_message=row[5],
        )

    def save_candidates(self, job_id: str, candidates: list[ClipCandidate]) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM clips WHERE job_id = ?", (job_id,))
            conn.executemany(
                """
                INSERT INTO clips (job_id, clip_id, start_sec, end_sec, title, hook, reason, score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        job_id,
                        c.clip_id,
                        c.start_sec,
                        c.end_sec,
                        c.title,
                        c.hook,
                        c.reason,
                        c.score,
                    )
                    for c in candidates
                ],
            )

    def save_rendered(self, job_id: str, rendered: list[RenderedClip]) -> None:
        with self._connect() as conn:
            conn.executemany(
                """
                UPDATE clips
                SET video_path = ?, subtitle_path = ?
                WHERE job_id = ? AND clip_id = ?
                """,
                [
                    (str(r.video_path), str(r.subtitle_path), job_id, r.clip_id)
                    for r in rendered
                ],
            )

    def get_review_rows(self, job_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT clip_id, start_sec, end_sec, title, score, hook, reason, video_path,
                       selected, edited_title
                FROM clips
                WHERE job_id = ?
                ORDER BY score DESC
                """,
                (job_id,),
            ).fetchall()

        return [
            {
                "clip_id": row[0],
                "start_sec": row[1],
                "end_sec": row[2],
                "title": row[3],
                "score": row[4],
                "hook": row[5],
                "reason": row[6],
                "video_path": row[7],
                "selected": bool(row[8]),
                "edited_title": row[9] or row[3],
            }
            for row in rows
        ]

    def save_review_decisions(self, job_id: str, decisions: list[ReviewDecision]) -> None:
        with self._connect() as conn:
            conn.executemany(
                """
                UPDATE clips
                SET selected = ?, edited_title = ?
                WHERE job_id = ? AND clip_id = ?
                """,
                [(1 if d.selected else 0, d.edited_title, job_id, d.clip_id) for d in decisions],
            )

    def load_selected_final(self, job_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT clip_id, start_sec, end_sec, title, edited_title, score, video_path
                FROM clips
                WHERE job_id = ? AND selected = 1
                ORDER BY score DESC
                """,
                (job_id,),
            ).fetchall()

        return [
            {
                "clip_id": row[0],
                "start_sec": row[1],
                "end_sec": row[2],
                "title": row[4] or row[3],
                "score": row[5],
                "video_path": row[6],
            }
            for row in rows
        ]
