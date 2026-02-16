from podcast_clip_factory.domain.clip_rules import ClipRuleConfig, ClipRuleEngine
from podcast_clip_factory.domain.models import ClipCandidate, Transcript, TranscriptSegment


def _transcript() -> Transcript:
    segments = [
        TranscriptSegment(start=0, end=25, text="導入"),
        TranscriptSegment(start=25, end=55, text="本題"),
        TranscriptSegment(start=55, end=90, text="オチ"),
        TranscriptSegment(start=90, end=140, text="追加トピック"),
        TranscriptSegment(start=140, end=200, text="まとめ"),
    ]
    return Transcript(segments=segments, duration_sec=200)


def test_rule_engine_caps_duration_and_title():
    engine = ClipRuleEngine(
        ClipRuleConfig(target_clips=12, min_clips=10, min_sec=30, max_sec=60, title_max_chars=28)
    )
    candidate = ClipCandidate(
        clip_id="a",
        start_sec=10,
        end_sec=120,
        title="これは非常に長いタイトルで二十八文字を超える可能性があるので切る",
        hook="h",
        reason="r",
        score=0.9,
    )

    result = engine.finalize([candidate], _transcript())
    assert result[0].duration == 60
    assert len(result[0].title) <= 28


def test_rule_engine_fills_to_min_clips():
    engine = ClipRuleEngine(
        ClipRuleConfig(target_clips=12, min_clips=10, min_sec=30, max_sec=60, title_max_chars=28)
    )
    seed = ClipCandidate(
        clip_id="seed",
        start_sec=0,
        end_sec=45,
        title="seed",
        hook="seed",
        reason="seed",
        score=0.8,
    )
    result = engine.finalize([seed], _transcript())
    assert len(result) >= 3  # duration 200secなので最低補完数はこの程度
    assert all(30 <= c.duration <= 60 for c in result)
