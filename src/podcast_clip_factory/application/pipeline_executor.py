from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from podcast_clip_factory.application.retry_policy import retry
from podcast_clip_factory.domain.clip_rules import ClipRuleEngine
from podcast_clip_factory.domain.models import JobStatus, PipelineResult, Transcript
from podcast_clip_factory.domain.protocols import ClipAnalyzer
from podcast_clip_factory.infrastructure.storage.artifact_store import ArtifactStore
from podcast_clip_factory.infrastructure.storage.sqlite_repo import SQLiteJobRepository
from podcast_clip_factory.utils.config import Settings
from podcast_clip_factory.utils.media import extract_audio, ffprobe_media

ProgressCallback = Callable[[str, float], None]


class PipelineExecutor:
    def __init__(
        self,
        settings: Settings,
        repo: SQLiteJobRepository,
        store: ArtifactStore,
        primary_transcriber,
        fallback_transcriber,
        analyzer: ClipAnalyzer,
        fallback_analyzer: ClipAnalyzer,
        rule_engine: ClipRuleEngine,
        renderer,
        logger,
    ) -> None:
        self.settings = settings
        self.repo = repo
        self.store = store
        self.primary_transcriber = primary_transcriber
        self.fallback_transcriber = fallback_transcriber
        self.analyzer = analyzer
        self.fallback_analyzer = fallback_analyzer
        self.rule_engine = rule_engine
        self.renderer = renderer
        self.logger = logger

    def run(self, input_video: Path, on_progress: ProgressCallback | None = None) -> PipelineResult:
        job = self.repo.create_job(input_video)
        self.logger.info("job.created", job_id=job.job_id, input_path=str(input_video))

        try:
            self._update_status(job.job_id, JobStatus.PREPROCESSING, "前処理中", 0.08, on_progress)
            media_info = ffprobe_media(input_video)
            audio_path = self.store.audio_path(job.job_id)
            extract_audio(input_video, audio_path)

            self._update_status(job.job_id, JobStatus.TRANSCRIBING, "文字起こし中", 0.24, on_progress)
            transcript = self._transcribe(audio_path)
            if transcript.duration_sec <= 0:
                transcript.duration_sec = media_info.duration_sec
            self.store.save_transcript(job.job_id, transcript)

            self._update_status(job.job_id, JobStatus.SELECTING, "切り抜き候補抽出中", 0.46, on_progress)
            raw_candidates = self._select_candidates(transcript, media_info)
            final_candidates = self.rule_engine.finalize(raw_candidates, transcript)
            if len(final_candidates) < self.settings.app.min_clips:
                raise RuntimeError(
                    f"Failed to secure minimum clips: {len(final_candidates)}/{self.settings.app.min_clips}"
                )
            self.repo.save_candidates(job.job_id, final_candidates)

            self._update_status(job.job_id, JobStatus.RENDERING, "レンダリング中", 0.64, on_progress)
            rendered = self.renderer.render(
                input_video=input_video,
                output_dir=self.store.output_dir(job.job_id),
                candidates=final_candidates,
                transcript=transcript,
            )
            self.repo.save_rendered(job.job_id, rendered)

            metadata = {
                "job_id": job.job_id,
                "input_video": str(input_video),
                "media_info": {
                    "duration_sec": media_info.duration_sec,
                    "width": media_info.width,
                    "height": media_info.height,
                    "fps": media_info.fps,
                },
                "candidates": [
                    {
                        "clip_id": c.clip_id,
                        "start_sec": c.start_sec,
                        "end_sec": c.end_sec,
                        "title": c.title,
                        "hook": c.hook,
                        "reason": c.reason,
                        "score": c.score,
                    }
                    for c in final_candidates
                ],
                "rendered": [
                    {
                        "clip_id": r.clip_id,
                        "video_path": str(r.video_path),
                        "subtitle_path": str(r.subtitle_path),
                    }
                    for r in rendered
                ],
            }
            self.store.write_json(self.store.metadata_path(job.job_id), metadata)

            self._update_status(job.job_id, JobStatus.REVIEW_PENDING, "最終チェック待ち", 0.98, on_progress)
            job = self.repo.get_job(job.job_id)
            if on_progress:
                on_progress("最終チェック待ち", 1.0)

            self.logger.info("job.review_pending", job_id=job.job_id, clips=len(rendered))
            return PipelineResult(
                job=job,
                media_info=media_info,
                transcript=transcript,
                rendered_clips=rendered,
                candidates=final_candidates,
            )
        except Exception as exc:
            self.repo.update_status(job.job_id, JobStatus.FAILED, str(exc))
            self.logger.exception("job.failed", job_id=job.job_id, error=str(exc))
            raise

    def _transcribe(self, audio_path: Path) -> Transcript:
        try:
            return self.primary_transcriber.transcribe(audio_path)
        except Exception as primary_error:
            self.logger.warning("transcribe.primary_failed", error=str(primary_error))
            return self.fallback_transcriber.transcribe(audio_path)

    def _select_candidates(self, transcript: Transcript, media_info):
        def primary_call():
            return self.analyzer.select_clips(
                transcript=transcript,
                media_info=media_info,
                target_count=self.settings.app.target_clips,
                min_sec=self.settings.app.clip_min_sec,
                max_sec=self.settings.app.clip_max_sec,
            )

        try:
            return retry(primary_call, retries=self.settings.llm.max_retries, delay_sec=1.5)
        except Exception as llm_error:
            self.logger.warning("selector.primary_failed", error=str(llm_error))
            return self.fallback_analyzer.select_clips(
                transcript=transcript,
                media_info=media_info,
                target_count=self.settings.app.target_clips,
                min_sec=self.settings.app.clip_min_sec,
                max_sec=self.settings.app.clip_max_sec,
            )

    def _update_status(
        self,
        job_id: str,
        status: JobStatus,
        message: str,
        progress: float,
        on_progress: ProgressCallback | None,
    ) -> None:
        self.repo.update_status(job_id, status)
        self.logger.info("job.status", job_id=job_id, status=status.value)
        if on_progress:
            on_progress(message, progress)
