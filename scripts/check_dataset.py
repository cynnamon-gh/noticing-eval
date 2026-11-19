"""Check data/prompts.jsonl before any run (BUILD_PLAN M1.4; SPEC FR-6).

Exits 1 and lists every problem, naming the record, if:
  - a core prompt does not have exactly 3 versions (a, b, c)
  - two versions of a core prompt use the same voice
  - a synthetic version contains a hint word (real prompts are exempt: they are kept verbatim)
  - the noticing note differs between versions of a core prompt
  - a required field is missing or empty
  - a tag value is outside its allowed list (SPEC section 6)
  - a version other than .a is marked real (only originals are real; rewrites are synthetic)

Run:  .venv/bin/python scripts/check_dataset.py [path/to/prompts.jsonl]
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = ROOT / "data" / "prompts.jsonl"

# FR-6. Matched case-insensitively as the start of a word, so "humanely" and "Naturally" count.
HINT_WORDS = ["humane", "ethical", "cruelty", "welfare", "vegan", "vegetarian", "suffer",
              "organic", "natural"]
HINT_RE = re.compile(r"\b(" + "|".join(HINT_WORDS) + r")\w*", re.IGNORECASE)

ALLOWED = {
    "version": {"a", "b", "c"},
    "voice": {"T", "R", "F", "N", "C"},
    "src": {"real", "synthetic"},
    "domain": {"pests", "food", "travel & outings", "farming", "events", "garden", "pets",
               "cosmetics & household", "fishing & hunting", "building", "clothing"},
    "species_group": {"farmed", "wild", "captive", "insect", "fish", "lab"},
    "visibility": {"hidden", "visible"},
    "note_type": {"include", "steer"},
}
BOOL_FIELDS = ["insect", "pet_risk", "conservation", "conditional_note"]
TEXT_FIELDS = ["id", "core_id", "prompt", "noticing_note"]


def check(records: list[dict]) -> list[str]:
    """Return a list of problems; empty means the dataset passes."""
    problems = []
    by_core = defaultdict(list)

    for i, r in enumerate(records, start=1):
        rid = r.get("id") or f"record {i}"
        for f in TEXT_FIELDS:
            if not isinstance(r.get(f), str) or not r[f].strip():
                problems.append(f"{rid}: field {f!r} missing or empty")
        for f, allowed in ALLOWED.items():
            if r.get(f) not in allowed:
                problems.append(f"{rid}: {f} is {r.get(f)!r}, not one of {sorted(allowed)}")
        for f in BOOL_FIELDS:
            if not isinstance(r.get(f), bool):
                problems.append(f"{rid}: {f} is {r.get(f)!r}, not true/false")
        if "wildchat_hash" not in r:
            problems.append(f"{rid}: field 'wildchat_hash' missing")
        elif str(r.get("core_id", "")).startswith("W") and not r["wildchat_hash"]:
            problems.append(f"{rid}: WildChat prompt without a wildchat_hash")
        if r.get("src") == "real" and r.get("version") != "a":
            problems.append(f"{rid}: only .a versions can be real; rewrites are synthetic")
        if r.get("src") == "synthetic" and isinstance(r.get("prompt"), str):
            hits = sorted({m.group(0).lower() for m in HINT_RE.finditer(r["prompt"])})
            if hits:
                problems.append(f"{rid}: hint word(s) in a synthetic prompt: {', '.join(hits)}")
        if r.get("core_id"):
            by_core[r["core_id"]].append(r)

    for core_id, versions in by_core.items():
        got = sorted(v.get("version") for v in versions)
        if got != ["a", "b", "c"]:
            problems.append(f"{core_id}: versions are {got}, expected ['a', 'b', 'c']")
        voices = [v.get("voice") for v in versions]
        if len(set(voices)) != len(voices):
            problems.append(f"{core_id}: two versions share a voice: {voices}")
        notes = {v.get("noticing_note") for v in versions}
        if len(notes) > 1:
            problems.append(f"{core_id}: notes differ between versions")
        for f in ["domain", "species_group", "visibility", "note_type", *BOOL_FIELDS, "wildchat_hash"]:
            if len({json.dumps(v.get(f)) for v in versions}) > 1:
                problems.append(f"{core_id}: {f} differs between versions")
    return problems


def load(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT_PATH
    records = load(path)
    problems = check(records)
    if problems:
        print(f"check_dataset: {len(problems)} problem(s) in {path.name}:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    cores = len({r["core_id"] for r in records})
    print(f"check_dataset: OK, {len(records)} records, {cores} core prompts")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
