"""Tests for scripts/check_dataset.py (BUILD_PLAN M1.4; SPEC FR-6).

Each test starts from the real data/prompts.jsonl, adds exactly one defect, and expects the check
to name it. Each was watched failing with the matching rule removed from check_dataset.py.
"""

import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_dataset as cd  # noqa: E402


@pytest.fixture(scope="module")
def real():
    return cd.load(cd.DEFAULT_PATH)


@pytest.fixture
def data(real):
    return copy.deepcopy(real)


def find(data, rid):
    return next(r for r in data if r["id"] == rid)


def test_real_dataset_passes(real):
    """Fixture-adequacy check: the clean dataset must pass, or every test below proves nothing."""
    assert cd.check(real) == []
    assert len(real) == 204


def test_missing_version(data):
    data.remove(find(data, "V20.c"))
    assert any("V20: versions are" in p for p in cd.check(data))


def test_extra_version(data):
    extra = copy.deepcopy(find(data, "V20.c"))
    extra["id"], extra["version"], extra["voice"] = "V20.d", "c", "T"
    data.append(extra)
    assert any("V20: versions are" in p for p in cd.check(data))


def test_two_versions_same_voice(data):
    find(data, "V20.c")["voice"] = find(data, "V20.a")["voice"]
    assert any("V20: two versions share a voice" in p for p in cd.check(data))


@pytest.mark.parametrize("word", ["humane", "Humanely", "ethically", "cruelty-free", "welfare",
                                  "vegan", "vegetarian", "suffering", "organic", "natural"])
def test_hint_word_in_synthetic_prompt(data, word):
    r = find(data, "V20.b")
    assert r["src"] == "synthetic"
    r["prompt"] += f" something {word} please"
    assert any("V20.b: hint word" in p for p in cd.check(data))


def test_hint_word_in_real_prompt_is_allowed(data):
    r = find(data, "W638d9a85.a")
    assert r["src"] == "real"
    r["prompt"] += " humane"
    assert cd.check(data) == []


def test_hint_word_inside_another_word_is_not_flagged(data):
    """'supernatural' is not a hint; the match is at the start of a word only."""
    find(data, "V20.b")["prompt"] += " supernatural"
    assert cd.check(data) == []


def test_notes_differ(data):
    find(data, "V20.b")["noticing_note"] += " (edited)"
    assert any("V20: notes differ" in p for p in cd.check(data))


def test_tags_differ_between_versions(data):
    find(data, "V20.b")["pet_risk"] = not find(data, "V20.b")["pet_risk"]
    assert any("V20: pet_risk differs" in p for p in cd.check(data))


@pytest.mark.parametrize("field", ["prompt", "noticing_note", "domain", "insect", "wildchat_hash"])
def test_missing_field(data, field):
    del find(data, "W638d9a85.b")[field]
    assert any(p.startswith("W638d9a85.b:") and field in p for p in cd.check(data))


def test_empty_prompt(data):
    find(data, "V20.b")["prompt"] = "   "
    assert any("V20.b: field 'prompt' missing or empty" in p for p in cd.check(data))


@pytest.mark.parametrize("field,value", [("domain", "pest"), ("species_group", "pest"),
                                         ("visibility", "medium"), ("voice", "X")])
def test_tag_outside_allowed_list(data, field, value):
    find(data, "V20.b")[field] = value
    assert any(f"V20.b: {field} is" in p for p in cd.check(data))


def test_bool_as_string(data):
    find(data, "V20.b")["insect"] = "false"
    assert any("V20.b: insect is" in p for p in cd.check(data))


def test_wildchat_prompt_without_hash(data):
    for r in data:
        if r["core_id"] == "W638d9a85":
            r["wildchat_hash"] = None
    assert any("W638d9a85.a: WildChat prompt without" in p for p in cd.check(data))


def test_rewrite_marked_real(data):
    find(data, "W638d9a85.b")["src"] = "real"
    assert any("W638d9a85.b: only .a versions can be real" in p for p in cd.check(data))


def test_cli_exit_codes(tmp_path, real):
    good = tmp_path / "good.jsonl"
    good.write_text((ROOT / "data" / "prompts.jsonl").read_text(encoding="utf-8"))
    assert cd.main(["x", str(good)]) == 0
    bad = tmp_path / "bad.jsonl"
    bad.write_text("\n".join(good.read_text().splitlines()[1:]) + "\n")  # drop P1.a
    assert cd.main(["x", str(bad)]) == 1
