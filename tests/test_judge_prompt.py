"""Tests for noticing/judge_prompt.py (BUILD_PLAN M2.2). Each was watched failing with its bug put back."""

import inspect
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import noticing.judge_prompt as jp  # noqa: E402


@pytest.fixture
def copies(tmp_path, monkeypatch):
    """Point the module at copies of the rubric and template, so tests can edit them safely."""
    rubric, template = tmp_path / "rubric.md", tmp_path / "prompt_template.txt"
    shutil.copy(jp.RUBRIC, rubric)
    shutil.copy(jp.TEMPLATE, template)
    monkeypatch.setattr(jp, "RUBRIC", rubric)
    monkeypatch.setattr(jp, "TEMPLATE", template)
    return rubric, template


def test_render_contains_all_inputs():
    out = jp.render("PROMPT-X", "NOTE-Y", "ANSWER-Z", pet_risk=False)
    for s in ("PROMPT-X", "NOTE-Y", "ANSWER-Z", "## The score: 0, 1 or 2"):
        assert s in out
    assert "<<" not in out, "a marker was left unreplaced"


def test_render_has_no_model_argument():
    """FR-10: the judge never sees which model wrote the answer.
    Break: add a `model` parameter to render()."""
    assert list(inspect.signature(jp.render).parameters) == ["prompt", "note", "answer", "pet_risk"]


def test_companion_harm_instruction_follows_pet_risk():
    """Break: always use COMPANION_HARM_ON."""
    assert jp.COMPANION_HARM_ON in jp.render("p", "n", "a", pet_risk=True)
    off = jp.render("p", "n", "a", pet_risk=False)
    assert jp.COMPANION_HARM_OFF in off and jp.COMPANION_HARM_ON not in off


def test_marker_text_inside_answer_is_not_expanded():
    """An answer that happens to contain '<<NOTE>>' must reach the judge unchanged.
    Break: replace markers one at a time with str.replace, answer before note."""
    out = jp.render("p", "THE-NOTE", "see <<NOTE>> and <<RUBRIC>>", pet_risk=False)
    assert "see <<NOTE>> and <<RUBRIC>>" in out
    assert out.count("THE-NOTE") == 1


@pytest.mark.parametrize("which", [0, 1])
def test_hash_changes_when_one_character_changes(copies, which):
    """NFR-3. Break: hash only the rubric (which=1 then stays equal)."""
    before = jp.judge_prompt_hash()
    path = copies[which]
    path.write_text(path.read_text() + " ")
    assert jp.judge_prompt_hash() != before


def test_hash_is_stable():
    assert jp.judge_prompt_hash() == jp.judge_prompt_hash()


def test_missing_marker_fails(copies):
    """Break: drop the missing-marker check -> the answer silently never reaches the judge."""
    _, template = copies
    template.write_text(template.read_text().replace("<<ANSWER>>", ""))
    with pytest.raises(ValueError, match="ANSWER"):
        jp.render("p", "n", "a", pet_risk=False)


def test_rubric_keeps_the_rules_design_md_requires():
    """FR-10 lists what the rubric must contain. Guards against an edit that drops a rule."""
    rubric = jp.RUBRIC.read_text()
    for heading in ("## The score: 0, 1 or 2", "### Clarifying questions", "### Byproducts",
                    "### Insects", "**`preachy`**", "**`companion_harm`**", "**`clarify_only`**",
                    "Any one option the note lists is enough"):
        assert heading in rubric, heading


def test_current_rubric_is_logged():
    """FR-16: every rubric version must be in judge/RUBRIC_LOG.md. Fails if the rubric or template
    is edited without logging the new hash. Break: add a space to judge/rubric.md."""
    log = (ROOT / "judge" / "RUBRIC_LOG.md").read_text()
    assert jp.judge_prompt_hash() in log, "rubric changed but judge/RUBRIC_LOG.md has no entry for it"
