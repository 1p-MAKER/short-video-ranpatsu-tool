from pathlib import Path

import pytest

from podcast_clip_factory.infrastructure.llm.gemini_client import GeminiClipAnalyzer


def _analyzer() -> GeminiClipAnalyzer:
    return GeminiClipAnalyzer(
        api_key="dummy",
        model="gemini-2.5-flash",
        prompt_path=Path("prompts/clip_selector.md"),
        json_repair=True,
    )


def test_parse_candidates_accepts_markdown_json_fence():
    analyzer = _analyzer()
    response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": "```json\n"
                            '[{"start_sec":1,"end_sec":40,"title":"t","hook":"h","reason":"r","score":0.9}]\n'
                            "```"
                        }
                    ]
                }
            }
        ]
    }
    clips = analyzer._parse_candidates(response)
    assert len(clips) == 1
    assert clips[0].start_sec == 1
    assert clips[0].end_sec == 40


def test_parse_candidates_accepts_object_with_clips_key():
    analyzer = _analyzer()
    response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": '{"clips":[{"start_sec":5,"end_sec":55,"title":"t","hook":"h","reason":"r","score":0.7}]}'
                        }
                    ]
                }
            }
        ]
    }
    clips = analyzer._parse_candidates(response)
    assert len(clips) == 1
    assert clips[0].clip_id == "llm_01"


def test_parse_candidates_raises_on_empty_content():
    analyzer = _analyzer()
    with pytest.raises(RuntimeError, match="Gemini response body was empty"):
        analyzer._parse_candidates({"candidates": [{"content": {"parts": []}}]})
