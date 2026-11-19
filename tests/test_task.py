"""Tests for noticing/task.py (BUILD_PLAN M2.1). All run on mockllm, Inspect's fake model: $0.

Each was watched failing with the matching behaviour broken in task.py.
"""

import sys
from pathlib import Path

import pytest
from inspect_ai import eval as inspect_eval

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from noticing.task import WELFARE_SYSTEM_PROMPT, load_samples, model_families, noticing  # noqa: E402


def run(tmp_path, **task_args):
    [log] = inspect_eval(noticing(judge=False, **task_args), model="mockllm/model", log_dir=str(tmp_path),
                         display="none")
    assert log.status == "success"
    return log


def test_one_user_message_no_system_prompt_no_settings(tmp_path):
    """FR-7. Break: add system_message(...) or generate(temperature=0) to the default solver."""
    log = run(tmp_path, epochs=1)
    assert len(log.samples) == 234
    for s in log.samples:
        assert [m.role for m in s.messages] == ["user", "assistant"], s.id
        assert s.messages[0].text == s.metadata["prompt"]
    assert {k: v for k, v in log.plan.config.model_dump().items() if v is not None} == {}
    # The settings actually sent with each model call. log.plan.config alone misses settings
    # passed to generate() in the solver (found by the break matrix, 2026-11-19).
    for s in log.samples:
        calls = [e for e in s.events if e.event == "model"]
        assert len(calls) == 1, s.id
        assert {k: v for k, v in calls[0].config.model_dump().items() if v is not None} == {}, s.id


def test_default_epochs_is_three(tmp_path):
    """FR-8. Break: change DEFAULT_EPOCHS. Runs 2 core prompts only, to stay fast."""
    log = run(tmp_path, core_ids="P1,V20")
    assert len(log.samples) == 2 * 3 * 3  # 2 core prompts x 3 versions x 3 epochs
    assert log.eval.metadata["epochs"] == 3


def test_pilot_slice_originals_only():
    """The pilot runs .a versions only. Break: ignore `versions` in load_samples."""
    ds = load_samples(versions="a")
    assert len(ds) == 78
    assert {s.metadata["version"] for s in ds} == {"a"}


def test_core_id_slice():
    ds = load_samples(core_ids="P1, V20")
    assert sorted(s.id for s in ds) == ["P1.a", "P1.b", "P1.c", "V20.a", "V20.b", "V20.c"]


@pytest.mark.parametrize("kwargs", [{"core_ids": "P1,NOPE"}, {"versions": "a,d"}])
def test_typo_in_slice_fails(kwargs):
    """A typo must not run an empty or partial slice. Break: remove the unknown-ID checks."""
    with pytest.raises(ValueError, match="unknown"):
        load_samples(**kwargs)


def test_welfare_system_prompt_only_when_asked(tmp_path):
    """FR-23. Break: drop the system_message from the welfare branch."""
    log = run(tmp_path, epochs=1, versions="a", core_ids="P1", welfare_system_prompt=True)
    [s] = log.samples
    assert [m.role for m in s.messages] == ["system", "user", "assistant"]
    assert s.messages[0].text == WELFARE_SYSTEM_PROMPT


def test_log_records_dataset_version(tmp_path):
    """NFR-3. Break: drop dataset_version from Task metadata."""
    log = run(tmp_path, epochs=1, core_ids="P1")
    expected = (ROOT / "data" / "DATASET_VERSION").read_text().strip()
    assert log.eval.metadata["dataset_version"] == expected
    assert log.eval.model == "mockllm/model"


def test_sample_metadata_carries_tags(tmp_path):
    """Analysis groups by these tags (FR-19). Break: metadata={} in record_to_sample."""
    [s] = load_samples(versions="a", core_ids="W638d9a85")
    for f in ["core_id", "noticing_note", "voice", "src", "domain", "visibility", "pet_risk",
              "wildchat_hash"]:
        assert f in s.metadata, f
    assert s.metadata["src"] == "real"


def test_every_model_has_a_family():
    """FR-12 routing needs a family for each model. Break: delete a family key in models.yaml."""
    fams = model_families()
    assert len(fams) >= 8
    assert all(fams.values())
