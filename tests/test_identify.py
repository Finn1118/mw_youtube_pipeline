from __future__ import annotations

from types import SimpleNamespace

from speaker_extraction import identify


def test_build_snippet_groups_and_cuts_off(sample_utterances: list[dict]) -> None:
    utterances = sample_utterances + [
        {
            "speaker": 0,
            "start": 150.0,
            "end": 155.0,
            "transcript": "This should not be included.",
            "confidence": 0.9,
        }
    ]
    snippet = identify._build_snippet(utterances, seconds=120)
    assert "Speaker 0:" in snippet
    assert "Speaker 1:" in snippet
    assert "should not be included" not in snippet


def test_is_intro_line_detects_common_intros() -> None:
    assert identify._is_intro_line("Joe Rogan podcast. Check it out.")
    assert identify._is_intro_line("The Joe Rogan Experience")
    assert identify._is_intro_line("   ")
    assert not identify._is_intro_line("Hello Sam, thanks for coming.")


def test_sample_speaker_lines_skips_intros_and_spreads(sample_utterances: list[dict]) -> None:
    utterances = sample_utterances + [
        {
            "speaker": 0,
            "start": 0.0,
            "end": 3.0,
            "transcript": "Joe Rogan podcast. Check it out.",
            "confidence": 0.9,
        }
    ]
    samples = identify._sample_speaker_lines(utterances, speaker=0, max_lines=3)
    assert all("Joe Rogan podcast" not in line for line in samples)


def test_build_identification_context_includes_stats_and_samples(
    sample_utterances: list[dict], video_info: dict
) -> None:
    context = identify._build_identification_context(sample_utterances, video_info)
    assert "Speaker 0:" in context
    assert "Speaker 1:" in context
    assert "YouTube title:" in context
    assert "Per-speaker profile" in context


def test_identify_speakers_parses_mapping_object(
    monkeypatch, sample_utterances: list[dict], video_info: dict
) -> None:
    captured: dict = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured["model"] = kwargs["model"]
            captured["messages"] = kwargs["messages"]
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content='{"mapping": {"0": "Host Name", "1": "Guest Name"}}'
                        )
                    )
                ]
            )

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        def __init__(self):
            self.chat = FakeChat()

    monkeypatch.setattr(identify, "OpenAI", FakeClient)
    mapping = identify.identify_speakers(sample_utterances, video_info)
    assert mapping == {0: "Host Name", 1: "Guest Name"}
    assert captured["model"] == "gpt-5.4-mini"
    assert any(msg["role"] == "system" for msg in captured["messages"])


def test_identify_with_fallback_stays_when_confident(
    monkeypatch, sample_utterances: list[dict], video_info: dict
) -> None:
    calls: list[str] = []

    def fake_identify(utterances, info, model="gpt-5.4-mini"):
        _ = utterances, info
        calls.append(model)
        return {0: "Host Name", 1: "Guest Name"}

    monkeypatch.setattr(identify, "identify_speakers", fake_identify)
    mapping = identify.identify_with_fallback(sample_utterances, video_info)
    assert calls == ["gpt-5.4-mini"]
    assert mapping == {0: "Host Name", 1: "Guest Name"}


def test_identify_with_fallback_escalates_on_all_unknown(
    monkeypatch, sample_utterances: list[dict], video_info: dict
) -> None:
    calls: list[str] = []

    def fake_identify(utterances, info, model="gpt-5.4-mini"):
        _ = utterances, info
        calls.append(model)
        if model == "gpt-5.4-mini":
            return {0: "Unknown", 1: "Unknown"}
        return {0: "Host Name", 1: "Guest Name"}

    monkeypatch.setattr(identify, "identify_speakers", fake_identify)
    mapping = identify.identify_with_fallback(sample_utterances, video_info)
    assert calls == ["gpt-5.4-mini", "gpt-5.4"]
    assert mapping[0] == "Host Name"


def test_identify_with_fallback_escalates_on_duplicate_names(
    monkeypatch, sample_utterances: list[dict], video_info: dict
) -> None:
    calls: list[str] = []

    def fake_identify(utterances, info, model="gpt-5.4-mini"):
        _ = utterances, info
        calls.append(model)
        if model == "gpt-5.4-mini":
            return {0: "Joe Rogan", 1: "Joe Rogan"}
        return {0: "Joe Rogan", 1: "Sam Altman"}

    monkeypatch.setattr(identify, "identify_speakers", fake_identify)
    mapping = identify.identify_with_fallback(sample_utterances, video_info)
    assert calls == ["gpt-5.4-mini", "gpt-5.4"]
    assert mapping == {0: "Joe Rogan", 1: "Sam Altman"}
