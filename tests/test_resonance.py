import pytest

from src.models import Aesthetic, Agent, Personality
from src.social.resonance import (
    aesthetic_compat,
    comment_threshold,
    interest_overlap,
    like_threshold,
    resonance_score,
)


def _make_agent(interests, palette="warm", composition="minimal", energy=0.5):
    return Agent(
        id="x", name="test", age=25,
        personality=Personality(energy=energy, valence=0.5, openness=0.5),
        interests=interests,
        aesthetic=Aesthetic(palette=palette, composition=composition),
        caption_style="concise", post_freq=1.0,
    )


def test_interest_overlap_identical():
    a = _make_agent({"사진": 0.8, "음식": 0.5})
    assert interest_overlap(a, a) == pytest.approx(1.0, abs=0.01)


def test_interest_overlap_no_shared():
    a = _make_agent({"사진": 0.8})
    b = _make_agent({"음식": 0.8})
    assert interest_overlap(a, b) == 0.0


def test_aesthetic_compat_same():
    a = _make_agent({}, "warm", "minimal")
    assert aesthetic_compat(a, a) == 1.0


def test_aesthetic_compat_different():
    a = _make_agent({}, "warm", "minimal")
    b = _make_agent({}, "cool", "busy")
    assert aesthetic_compat(a, b) < 1.0


def test_resonance_score_range():
    a = _make_agent({"사진": 0.8, "음식": 0.5})
    b = _make_agent({"사진": 0.7, "여행": 0.4})
    score = resonance_score(a, b)
    assert 0.0 <= score <= 1.0


def test_like_threshold_extrovert_lower():
    introverted = _make_agent({}, energy=0.1)
    extroverted = _make_agent({}, energy=0.9)
    assert like_threshold(extroverted) < like_threshold(introverted)


def test_comment_threshold_higher_than_like():
    agent = _make_agent({}, energy=0.5)
    assert comment_threshold(agent) > like_threshold(agent)


def test_interest_overlap_symmetric():
    a = _make_agent({"사진": 0.8, "음식": 0.5})
    b = _make_agent({"사진": 0.7, "여행": 0.4})
    assert interest_overlap(a, b) == pytest.approx(interest_overlap(b, a), abs=0.01)
