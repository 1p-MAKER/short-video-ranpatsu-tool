from podcast_clip_factory.domain.models import MediaInfo, Transcript, TranscriptSegment
from podcast_clip_factory.infrastructure.llm.fallback_client import HeuristicClipAnalyzer


def test_fallback_analyzer_handles_empty_transcript_with_duration():
    analyzer = HeuristicClipAnalyzer()
    transcript = Transcript(segments=[], duration_sec=600)
    media = MediaInfo(duration_sec=600, width=1920, height=1080, fps=30)

    clips = analyzer.select_clips(
        transcript=transcript,
        media_info=media,
        target_count=12,
        min_sec=30,
        max_sec=60,
    )

    assert len(clips) == 12
    assert all(30 <= (c.end_sec - c.start_sec) <= 60 for c in clips)


def test_fallback_analyzer_with_segments_returns_candidates():
    analyzer = HeuristicClipAnalyzer()
    transcript = Transcript(
        segments=[
            TranscriptSegment(start=0, end=40, text="alpha"),
            TranscriptSegment(start=40, end=90, text="beta"),
            TranscriptSegment(start=90, end=140, text="gamma"),
        ],
        duration_sec=140,
    )
    media = MediaInfo(duration_sec=140, width=1920, height=1080, fps=30)

    clips = analyzer.select_clips(
        transcript=transcript,
        media_info=media,
        target_count=4,
        min_sec=30,
        max_sec=60,
    )

    assert clips
