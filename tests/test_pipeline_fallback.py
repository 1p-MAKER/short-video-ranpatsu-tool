from pathlib import Path

from podcast_clip_factory.application.pipeline_executor import PipelineExecutor
from podcast_clip_factory.domain.clip_rules import ClipRuleConfig, ClipRuleEngine
from podcast_clip_factory.domain.models import ClipCandidate, MediaInfo, Transcript, TranscriptSegment
from podcast_clip_factory.utils.config import (
    AppConfig,
    LLMConfig,
    RenderConfig,
    Settings,
    SubtitleConfig,
    TranscribeConfig,
)


class FailingAnalyzer:
    def select_clips(self, transcript, media_info, target_count, min_sec, max_sec):
        raise RuntimeError("boom")


class WorkingAnalyzer:
    def select_clips(self, transcript, media_info, target_count, min_sec, max_sec):
        return [
            ClipCandidate(
                clip_id="f1",
                start_sec=0,
                end_sec=40,
                title="ok",
                hook="hook",
                reason="fallback",
                score=0.5,
            )
        ]


class DummyTranscriber:
    def __init__(self):
        self.called = False

    def transcribe(self, audio_path: Path):
        self.called = True
        return Transcript(segments=[TranscriptSegment(start=0, end=40, text="t")], duration_sec=40)


class DummyRepo:
    def __init__(self):
        self.statuses = []

    def create_job(self, input_path):
        from podcast_clip_factory.domain.models import JobRecord, JobStatus

        return JobRecord(job_id="j1", input_path=input_path, status=JobStatus.QUEUED)

    def update_status(self, job_id, status, error_message=""):
        self.statuses.append(status.value)

    def save_candidates(self, job_id, candidates):
        pass

    def save_rendered(self, job_id, rendered):
        pass

    def get_job(self, job_id):
        from podcast_clip_factory.domain.models import JobRecord, JobStatus

        return JobRecord(job_id=job_id, input_path=Path("in.mp4"), status=JobStatus.REVIEW_PENDING)


class DummyStore:
    def audio_path(self, job_id):
        return Path("audio.wav")

    def save_transcript(self, job_id, transcript):
        return Path("transcript.json")

    def output_dir(self, job_id):
        return Path("out")

    def metadata_path(self, job_id):
        return Path("meta.json")

    def write_json(self, path, payload):
        pass


class DummyRenderer:
    def render(self, input_video, output_dir, candidates, transcript):
        return []


class DummyLogger:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def exception(self, *args, **kwargs):
        pass


def test_select_candidates_falls_back_to_secondary_analyzer():
    settings = Settings(
        app=AppConfig(12, 10, 30, 60, 28, 3, True, 1),
        transcribe=TranscribeConfig("mlx", "faster", True, "m", "f"),
        llm=LLMConfig("gemini", "heuristic", False, 0, True, "g", "", ""),
        render=RenderConfig(1080, 1920, 1080, 608, 40, "h264_videotoolbox", "aac", "192k"),
        subtitle=SubtitleConfig(False, "Hiragino Sans", 52, "&H0039C1FF", "&H00FFFFFF", "&H00000000", 220),
        root_dir=Path("."),
    )

    executor = PipelineExecutor(
        settings=settings,
        repo=DummyRepo(),
        store=DummyStore(),
        primary_transcriber=DummyTranscriber(),
        fallback_transcriber=DummyTranscriber(),
        analyzer=FailingAnalyzer(),
        fallback_analyzer=WorkingAnalyzer(),
        rule_engine=ClipRuleEngine(ClipRuleConfig(12, 10, 30, 60, 28)),
        renderer=DummyRenderer(),
        logger=DummyLogger(),
    )

    transcript = Transcript([TranscriptSegment(start=0, end=40, text="x")], duration_sec=40)
    media_info = MediaInfo(duration_sec=40, width=1920, height=1080, fps=30)
    selected = executor._select_candidates(transcript, media_info)
    assert selected[0].clip_id == "f1"
