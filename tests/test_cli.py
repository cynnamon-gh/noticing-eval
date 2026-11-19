"""Run the eval the way a person does: the `inspect eval` command, not a Python import.

Added 2026-11-19, after the first real run failed with "No module named 'noticing'": every other
test imported the task from Python with the project folder on sys.path, so none of them could see
that the command line could not find the package. Uses mockllm, so it costs $0.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSPECT = Path(sys.executable).parent / "inspect"


def test_inspect_eval_command_runs(tmp_path):
    """Break: uninstall the package (pip uninstall noticing-eval) -> ModuleNotFoundError."""
    result = subprocess.run(
        [str(INSPECT), "eval", "noticing/task.py", "--model", "mockllm/model",
         "-T", "judge=false", "-T", "epochs=1", "-T", "versions=a", "-T", "core_ids=P1",
         "--log-dir", str(tmp_path), "--display", "none"],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert list(tmp_path.glob("*.eval")), "no log written"
