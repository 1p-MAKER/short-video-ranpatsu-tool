from podcast_clip_factory.domain.models import ClipCandidate, Transcript, TranscriptSegment
from podcast_clip_factory.infrastructure.render.subtitle_generator import SubtitleGenerator
from podcast_clip_factory.utils.config import SubtitleConfig


def _generator() -> SubtitleGenerator:
    return SubtitleGenerator(
        SubtitleConfig(
            enable_subtitles=True,
            font_name="Hiragino Sans",
            font_size=52,
            highlight_color="&H0039C1FF",
            primary_color="&H00FFFFFF",
            outline_color="&H00000000",
            bottom_margin=220,
        )
    )


def test_subtitle_lines_are_remapped_after_compaction():
    gen = _generator()
    candidate = ClipCandidate("c1", 0, 20, "t", "h", "r", 0.9)
    transcript = Transcript(
        segments=[
            TranscriptSegment(start=0.0, end=4.0, text="a"),
            TranscriptSegment(start=6.0, end=9.0, text="b"),
        ],
        duration_sec=20.0,
    )
    # Keep [0-5] and [8-12] -> timeline after compaction is [0-9]
    speech_intervals = [(0.0, 5.0), (8.0, 12.0)]

    lines = gen._build_dialogue_lines(candidate, transcript, speech_intervals=speech_intervals)

    # "a" should stay at 0-4
    assert lines[0][0] == 0.0
    assert lines[0][1] == 4.0
    # "b" overlaps second kept interval [8-9], mapped to [5-6]
    assert lines[1][0] == 5.0
    assert lines[1][1] == 6.0
