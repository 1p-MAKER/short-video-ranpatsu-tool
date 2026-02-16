from pathlib import Path

from podcast_clip_factory.domain.models import ClipCandidate
from podcast_clip_factory.infrastructure.render.ffmpeg_builder import FFmpegCommandBuilder
from podcast_clip_factory.utils.config import RenderConfig


def test_ffmpeg_command_contains_letterbox_filter_and_codec():
    cfg = RenderConfig(
        video_width=1080,
        video_height=1920,
        center_width=1080,
        center_height=608,
        background_blur_sigma=40,
        video_codec="h264_videotoolbox",
        audio_codec="aac",
        audio_bitrate="192k",
    )
    builder = FFmpegCommandBuilder(cfg)
    candidate = ClipCandidate(
        clip_id="c1",
        start_sec=12.5,
        end_sec=72.3,
        title="タイトル",
        hook="h",
        reason="r",
        score=0.8,
    )

    cmd = builder.build(Path("in.mp4"), Path("out.mp4"), Path("sub.ass"), candidate)

    assert "-filter_complex" in cmd
    assert "h264_videotoolbox" in cmd
    assert any("gblur=sigma=40" in token for token in cmd)
