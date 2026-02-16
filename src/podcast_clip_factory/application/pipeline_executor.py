from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from threading import Event, Thread
from time import monotonic

from podcast_clip_factory.application.retry_policy import retry
from podcast_clip_factory.domain.clip_rules import ClipRuleEngine
from podcast_clip_factory.domain.models import JobStatus, PipelineResult, Transcript
from podcast_clip_factory.domain.protocols import ClipAnalyzer
from podcast_clip_factory.infrastructure.storage.artifact_store import ArtifactStore
from podcast_clip_factory.infrastructure.storage.sqlite_repo import SQLiteJobRepository
from podcast_clip_factory.utils.config import Settings
from podcast_clip_factory.utils.media import extract_audio, ffprobe_media

ProgressCallback = Callable[[str, float], None]
LogCallback = Callable[[str], None]


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

    def run(
        self,
        input_video: Path,
        on_progress: ProgressCallback | None = None,
        on_log: LogCallback | None = None,
    ) -> PipelineResult:
        job = self.repo.create_job(input_video)
        self.logger.info("job.created", job_id=job.job_id, input_path=str(input_video))
        self._emit_log(on_log, f"ジョブ作成: {job.job_id}")

        try:
            self._update_status(
                job.job_id,
                JobStatus.PREPROCESSING,
                "前処理中（通常 10-30秒）",
                0.08,
                on_progress,
                on_log,
            )
            media_info = ffprobe_media(input_video)
            audio_path = self.store.audio_path(job.job_id)
            self._emit_log(
                on_log,
                (
                    f"入力動画: {media_info.duration_sec / 60:.1f}分 / "
                    f"{media_info.width}x{media_info.height} / {media_info.fps:.2f}fps"
                ),
            )
            self._emit_log(
                on_log,
                f"想定所要時間: {self._estimate_total_minutes(media_info.duration_sec):.1f}分前後",
            )
            extract_audio(input_video, audio_path)
            self._emit_log(on_log, "音声抽出が完了しました")

            self._update_status(
                job.job_id,
                JobStatus.TRANSCRIBING,
                "文字起こし中（通常 2-8分）",
                0.24,
                on_progress,
                on_log,
            )
            transcript = self._run_with_heartbeat(
                operation=lambda: self._transcribe(audio_path, on_log=on_log),
                phase_label="文字起こし",
                base_progress=0.24,
                on_progress=on_progress,
                on_log=on_log,
            )
            if transcript.duration_sec <= 0:
                transcript.duration_sec = media_info.duration_sec
            self.store.save_transcript(job.job_id, transcript)
            self._emit_log(on_log, "文字起こしを保存しました")

            self._update_status(
                job.job_id,
                JobStatus.SELECTING,
                "切り抜き候補抽出中（通常 10-60秒）",
                0.46,
                on_progress,
                on_log,
            )
            raw_candidates = self._run_with_heartbeat(
                operation=lambda: self._select_candidates(transcript, media_info, on_log=on_log),
                phase_label="候補抽出",
                base_progress=0.46,
                on_progress=on_progress,
                on_log=on_log,
            )
            final_candidates = self.rule_engine.finalize(raw_candidates, transcript)
            if len(final_candidates) < self.settings.app.min_clips:
                raise RuntimeError(
                    f"Failed to secure minimum clips: {len(final_candidates)}/{self.settings.app.min_clips}"
                )
            self._emit_log(
                on_log,
                (
                    f"候補抽出完了: {len(final_candidates)}件 "
                    f"(目標 {self.settings.app.target_clips}件 / 下限 {self.settings.app.min_clips}件)"
                ),
            )
            self.repo.save_candidates(job.job_id, final_candidates)

            self._update_status(
                job.job_id,
                JobStatus.RENDERING,
                "レンダリング中（1本あたり 1-2分）",
                0.64,
                on_progress,
                on_log,
            )
            rendered = self._render_with_progress(
                input_video=input_video,
                job_id=job.job_id,
                candidates=final_candidates,
                transcript=transcript,
                on_progress=on_progress,
                on_log=on_log,
            )
            self.repo.save_rendered(job.job_id, rendered)
            self._emit_log(on_log, "レンダリングを保存しました")

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

            self._update_status(
                job.job_id,
                JobStatus.REVIEW_PENDING,
                "最終チェック待ち",
                0.98,
                on_progress,
                on_log,
            )
            job = self.repo.get_job(job.job_id)
            if on_progress:
                on_progress("最終チェック待ち", 1.0)
            self._emit_log(on_log, "最終チェック画面へ進んでください")

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
            self._emit_log(on_log, f"ジョブ失敗: {exc}")
            raise

    def _transcribe(self, audio_path: Path, on_log: LogCallback | None = None) -> Transcript:
        try:
            self._emit_log(on_log, "文字起こし: mlx-whisper を使用します")
            return self.primary_transcriber.transcribe(audio_path)
        except Exception as primary_error:
            self.logger.warning("transcribe.primary_failed", error=str(primary_error))
            self._emit_log(on_log, f"mlx-whisper失敗。faster-whisperに切替: {primary_error}")
            return self.fallback_transcriber.transcribe(audio_path)

    def _select_candidates(self, transcript: Transcript, media_info, on_log: LogCallback | None = None):
        def primary_call():
            return self.analyzer.select_clips(
                transcript=transcript,
                media_info=media_info,
                target_count=self.settings.app.target_clips,
                min_sec=self.settings.app.clip_min_sec,
                max_sec=self.settings.app.clip_max_sec,
            )

        try:
            self._emit_log(on_log, "候補抽出: Geminiを呼び出します")
            return retry(primary_call, retries=self.settings.llm.max_retries, delay_sec=1.5)
        except Exception as llm_error:
            self.logger.warning("selector.primary_failed", error=str(llm_error))
            self._emit_log(on_log, f"Gemini失敗。ヒューリスティックに切替: {llm_error}")
            return self.fallback_analyzer.select_clips(
                transcript=transcript,
                media_info=media_info,
                target_count=self.settings.app.target_clips,
                min_sec=self.settings.app.clip_min_sec,
                max_sec=self.settings.app.clip_max_sec,
            )

    def _render_with_progress(
        self,
        input_video: Path,
        job_id: str,
        candidates,
        transcript: Transcript,
        on_progress: ProgressCallback | None,
        on_log: LogCallback | None,
    ):
        total = len(candidates)
        completed = 0

        if on_progress:
            on_progress(f"レンダリング中 0/{total}", 0.64)
        self._emit_log(
            on_log,
            f"レンダリング開始: {total}本 / 並列 {self.settings.app.render_parallelism}",
        )

        def on_event(kind: str, idx: int, event_total: int, title: str) -> None:
            nonlocal completed
            if kind == "started":
                self._emit_log(on_log, f"レンダリング開始 {idx}/{event_total}: {title}")
                return
            if kind == "completed":
                completed += 1
                progress = 0.64 + 0.32 * (completed / max(event_total, 1))
                if on_progress:
                    on_progress(f"レンダリング中 {completed}/{event_total}", progress)
                self._emit_log(on_log, f"レンダリング完了 {completed}/{event_total}: {title}")
                return
            if kind == "failed":
                self._emit_log(on_log, f"レンダリング失敗 {idx}/{event_total}: {title}")

        try:
            return self.renderer.render(
                input_video=input_video,
                output_dir=self.store.output_dir(job_id),
                candidates=candidates,
                transcript=transcript,
                on_event=on_event,
            )
        except TypeError:
            # Backward-compatible path for renderers without progress callback support.
            return self.renderer.render(
                input_video=input_video,
                output_dir=self.store.output_dir(job_id),
                candidates=candidates,
                transcript=transcript,
            )

    def _run_with_heartbeat(
        self,
        operation,
        phase_label: str,
        base_progress: float,
        on_progress: ProgressCallback | None,
        on_log: LogCallback | None,
    ):
        finished = Event()
        result_holder: dict[str, object] = {}
        error_holder: dict[str, Exception] = {}

        def worker() -> None:
            try:
                result_holder["value"] = operation()
            except Exception as exc:  # pragma: no cover
                error_holder["error"] = exc
            finally:
                finished.set()

        Thread(target=worker, daemon=True).start()

        start = monotonic()
        last_log_elapsed = -15
        while not finished.wait(1.0):
            elapsed = int(monotonic() - start)
            if on_progress:
                on_progress(f"{phase_label} 実行中（{self._format_elapsed(elapsed)}経過）", base_progress)
            if elapsed - last_log_elapsed >= 15:
                self._emit_log(on_log, f"{phase_label} 実行中（{self._format_elapsed(elapsed)}経過）")
                last_log_elapsed = elapsed

        if "error" in error_holder:
            raise error_holder["error"]
        return result_holder.get("value")

    def _estimate_total_minutes(self, duration_sec: float) -> float:
        # 50分入力で概ね15〜25分レンジに収まるような保守的見積り
        transcribe_min = max(2.0, duration_sec / 900.0)
        render_min = max(
            6.0,
            (self.settings.app.target_clips * 1.5) / max(self.settings.app.render_parallelism, 1),
        )
        misc_min = 1.5
        return transcribe_min + render_min + misc_min

    def _format_elapsed(self, total_sec: int) -> str:
        mins = total_sec // 60
        secs = total_sec % 60
        return f"{mins:02d}:{secs:02d}"

    def _emit_log(self, on_log: LogCallback | None, message: str) -> None:
        self.logger.info("job.log", message=message)
        if on_log:
            on_log(message)

    def _update_status(
        self,
        job_id: str,
        status: JobStatus,
        message: str,
        progress: float,
        on_progress: ProgressCallback | None,
        on_log: LogCallback | None,
    ) -> None:
        self.repo.update_status(job_id, status)
        self.logger.info("job.status", job_id=job_id, status=status.value)
        if on_progress:
            on_progress(message, progress)
        self._emit_log(on_log, message)
