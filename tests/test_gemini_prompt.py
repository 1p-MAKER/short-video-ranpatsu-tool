from pathlib import Path

from podcast_clip_factory.domain.models import MediaInfo, Transcript, TranscriptSegment
from podcast_clip_factory.infrastructure.llm.gemini_client import GeminiClipAnalyzer


def test_build_user_prompt_contains_timestamped_segments():
    analyzer = GeminiClipAnalyzer(
        api_key="dummy",
        model="gemini-2.5-flash",
        prompt_path=Path("prompts/clip_selector.md"),
        json_repair=True,
    )
    transcript = Transcript(
        segments=[
            TranscriptSegment(start=1.2, end=5.6, text="alpha"),
            TranscriptSegment(start=65.0, end=70.0, text="beta"),
        ],
        duration_sec=70.0,
    )
    media = MediaInfo(duration_sec=70.0, width=1920, height=1080, fps=30.0)

    prompt = analyzer._build_user_prompt(transcript, media, target_count=12, min_sec=30, max_sec=60)

    assert "TranscriptWithTimestamps:" in prompt
    assert "[00:01-00:05] alpha" in prompt
    assert "[01:05-01:10] beta" in prompt
