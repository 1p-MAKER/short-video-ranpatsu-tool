from pathlib import Path

from podcast_clip_factory.domain.models import ClipCandidate, Transcript, TranscriptSegment
from podcast_clip_factory.infrastructure.render.ffmpeg_builder import FFmpegCommandBuilder
from podcast_clip_factory.infrastructure.render.local_renderer import LocalFFmpegRenderer
from podcast_clip_factory.infrastructure.render.subtitle_generator import SubtitleGenerator
from podcast_clip_factory.utils.config import AppConfig, RenderConfig, SubtitleConfig


def _renderer() -> LocalFFmpegRenderer:
    app = AppConfig(
        target_clips=12,
        min_clips=10,
        clip_min_sec=30,
        clip_max_sec=60,
        title_max_chars=28,
        render_parallelism=1,
        manual_start_only=True,
        max_render_retries=1,
        enable_silence_compaction=True,
        silence_speech_pad_sec=0.1,
        silence_merge_gap_sec=0.2,
        silence_min_segment_sec=0.1,
        silence_min_cut_total_sec=0.5,
        silence_max_segments=24,
    )
    render = RenderConfig(
        video_width=1080,
        video_height=1920,
        center_width=1080,
        center_height=608,
        background_blur_sigma=40,
        video_codec="h264_videotoolbox",
        audio_codec="aac",
        audio_bitrate="192k",
    )
    subtitle = SubtitleConfig(
        enable_subtitles=False,
        font_name="Hiragino Sans",
        font_size=52,
        highlight_color="&H0039C1FF",
        primary_color="&H00FFFFFF",
        outline_color="&H00000000",
        bottom_margin=220,
    )
    return LocalFFmpegRenderer(
        app_config=app,
        command_builder=FFmpegCommandBuilder(render),
        subtitle_generator=SubtitleGenerator(subtitle),
        enable_subtitles=False,
    )


def test_build_speech_intervals_compacts_gaps():
    renderer = _renderer()
    candidate = ClipCandidate(
        clip_id="c1",
        start_sec=0,
        end_sec=60,
        title="t",
        hook="h",
        reason="r",
        score=0.9,
    )
    transcript = Transcript(
        segments=[
            TranscriptSegment(start=1, end=3, text="a"),
            TranscriptSegment(start=15, end=18, text="b"),
            TranscriptSegment(start=40, end=43, text="c"),
        ],
        duration_sec=60,
    )

    intervals = renderer._build_speech_intervals(candidate, transcript)
    assert intervals is not None
    assert len(intervals) == 3
    assert intervals[0][0] <= 1
    assert intervals[-1][1] >= 43


def test_ffmpeg_builder_uses_concat_when_speech_intervals_given():
    render = RenderConfig(1080, 1920, 1080, 608, 40, "h264_videotoolbox", "aac", "192k")
    builder = FFmpegCommandBuilder(render)
    candidate = ClipCandidate("c1", 0, 30, "title", "hook", "reason", 0.8, punchline="impact")
    cmd = builder.build(
        input_video=Path("in.mp4"),
        output_video=Path("out.mp4"),
        subtitle_path=None,
        candidate=candidate,
        speech_intervals=[(0.0, 5.0), (7.0, 12.0)],
    )
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "concat=n=2:v=1:a=1[srcv][srca]" in graph
    assert cmd[cmd.index("-map") + 3] == "[srca]"
