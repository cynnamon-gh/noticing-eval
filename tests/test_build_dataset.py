"""Tests for scripts/build_dataset.py (BUILD_PLAN M1.3).

Most tests run on the real project files, not invented rows. Each test was watched failing with
the bug it guards against put back in; the break is named in its docstring.
"""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build_dataset as bd  # noqa: E402


@pytest.fixture(scope="module")
def records():
    variants = bd.parse_variants(bd.VARIANTS_MD.read_text(encoding="utf-8"))
    return bd.build_records(variants, bd.load_core(bd.CORE_CSV))


def test_all_204_versions_parsed(records):
    """Break: tighten ROW so long or unusual rows stop matching -> count drops or parse error."""
    assert len(records) == 204
    assert len({r["core_id"] for r in records}) == 68


def test_real_prompts_are_verbatim(records):
    """FR-5. Every real (.a) prompt equals the verbatim text in wildchat-prompts.md.

    Break: strip or lowercase prompts in parse_variants -> mismatch.
    """
    wc = (ROOT / "data" / "sources" / "wildchat-prompts.md").read_text(encoding="utf-8")
    verbatim = {
        "W" + m.group(1): m.group(2).strip()
        for m in re.finditer(r"^\| ([0-9a-f]{8}) \| (.+?) \| [^|]+ \|$", wc, re.M)
    }
    real = {r["core_id"]: r["prompt"] for r in records if r["src"] == "real"}
    assert len(real) == 17  # 21 found in WildChat; 4 food ones trimmed on 2026-11-19
    assert set(real) <= set(verbatim)
    assert real == {k: verbatim[k] for k in real}


def test_real_versions_have_full_hash(records):
    """§6: real prompts and their rewrites carry the full 32-character hash; others carry None.

    Break: drop `or None` in load_core -> synthetic rows get "" instead of None.
    """
    for r in records:
        if r["core_id"].startswith("W"):
            assert re.fullmatch(r"[0-9a-f]{32}", r["wildchat_hash"]), r["id"]
            assert r["wildchat_hash"].startswith(r["core_id"][1:])
        else:
            assert r["wildchat_hash"] is None, r["id"]


def test_booleans_are_bool(records):
    """Break: remove the bool conversion in load_core -> fields stay the strings 'true'/'false'."""
    for r in records:
        for b in bd.BOOL_FIELDS:
            assert isinstance(r[b], bool), (r["id"], b)
    assert sum(r["insect"] for r in records) == 7 * 3  # 7 insect core prompts x 3 versions


def test_escaped_pipe_is_unescaped():
    """Break: drop the replace('\\\\|', '|') -> prompt keeps the backslash."""
    rows = bd.parse_variants("| X1.a | T | synthetic | cats \\| dogs |\n")
    assert rows[0]["prompt"] == "cats | dogs"


def test_bad_row_fails_loudly():
    """A typo must stop the build, not drop the row. Break: `continue` instead of raise."""
    with pytest.raises(bd.DatasetError, match="does not parse"):
        bd.parse_variants("| X1.a | T | synthetic | one | extra cell |\n")
    with pytest.raises(bd.DatasetError, match="unknown voice"):
        bd.parse_variants("| X1.a | Q | synthetic | hello |\n")


def test_unknown_core_id_fails(records):
    """Break: skip variants whose core_id is missing -> no error."""
    core = bd.load_core(bd.CORE_CSV)
    with pytest.raises(bd.DatasetError, match="not in core.csv"):
        bd.build_records([{"core_id": "ZZ9", "version": "a", "voice": "T",
                           "src": "synthetic", "prompt": "hi"}], core)


def test_output_is_deterministic(records):
    """Break: iterate a set somewhere in build_records -> order can change between runs."""
    variants = bd.parse_variants(bd.VARIANTS_MD.read_text(encoding="utf-8"))
    again = bd.build_records(list(reversed(variants)), bd.load_core(bd.CORE_CSV))
    assert bd.to_jsonl(again) == bd.to_jsonl(records)
