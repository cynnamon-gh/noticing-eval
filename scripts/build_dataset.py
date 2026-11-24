"""Build data/prompts.jsonl, the dataset Inspect reads (BUILD_PLAN M1.3; SPEC FR-1, FR-5, NFR-3).

Inputs:
  data/core.csv              one row per core prompt: note and tags (approved in M1.2)
  data/sources/voice-variants.md   204 rows: one per version (wording) of a core prompt

Outputs:
  data/prompts.jsonl         204 records, fields as in SPEC section 6
  data/DATASET_VERSION       SHA-256 of prompts.jsonl; the Inspect task writes it into every log

Run:  .venv/bin/python scripts/build_dataset.py
Running it twice gives byte-identical output.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE_CSV = ROOT / "data" / "core.csv"
VARIANTS_MD = ROOT / "data" / "sources" / "voice-variants.md"
OUT_JSONL = ROOT / "data" / "prompts.jsonl"
OUT_VERSION = ROOT / "data" / "DATASET_VERSION"

# Field order in each JSONL record (SPEC section 6).
FIELDS = [
    "id", "core_id", "version", "prompt", "noticing_note", "voice", "src", "wildchat_hash",
    "domain", "species_group", "visibility", "note_type",
    "insect", "pet_risk", "conservation", "conditional_note",
]
BOOL_FIELDS = ["insect", "pet_risk", "conservation", "conditional_note"]

# A version row: | P1.a | F | synthetic | How do I get rid of mice in my garage? |
# The prompt may contain "\|" (an escaped pipe); an unescaped pipe would split the cell.
ROW = re.compile(
    r"^\| (?P<core_id>[A-Za-z0-9]+)\.(?P<version>[abc]) \| (?P<voice>[^|]*?) \| (?P<src>[^|]*?) \| "
    r"(?P<prompt>(?:[^|\\]|\\.)*?) \|\s*$"
)
# Any line that looks like it starts a version row, valid or not.
ROW_START = re.compile(r"^\| [A-Za-z0-9]+\.[a-z] \|")


class DatasetError(Exception):
    """The inputs are inconsistent; the message names the row."""


def parse_variants(text: str) -> list[dict]:
    """Return one dict per version row in voice-variants.md.

    Fails on a row that starts like a version row but does not parse, or has an unknown voice or
    source, so a typo can't silently drop a prompt.
    """
    rows = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not ROW_START.match(line):
            continue
        m = ROW.match(line)
        if not m:
            raise DatasetError(f"voice-variants.md line {lineno}: row does not parse: {line[:80]}")
        row = m.groupdict()
        if row["voice"] not in {"T", "R", "F", "N", "C"}:
            raise DatasetError(f"line {lineno}: unknown voice {row['voice']!r}")
        if row["src"] not in {"real", "synthetic"}:
            raise DatasetError(f"line {lineno}: unknown src {row['src']!r}")
        row["prompt"] = row["prompt"].replace("\\|", "|").strip()
        if not row["prompt"]:
            raise DatasetError(f"line {lineno}: empty prompt")
        rows.append(row)
    return rows


def load_core(path: Path) -> dict[str, dict]:
    """Return core.csv as {core_id: row}, with booleans as bool and an empty hash as None."""
    core = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for b in BOOL_FIELDS:
                if row[b] not in {"true", "false"}:
                    raise DatasetError(f"core.csv {row['core_id']}: {b} is {row[b]!r}, not true/false")
                row[b] = row[b] == "true"
            row["wildchat_hash"] = row["wildchat_hash"] or None
            if row["core_id"] in core:
                raise DatasetError(f"core.csv: duplicate core_id {row['core_id']}")
            core[row["core_id"]] = row
    return core


def build_records(variants: list[dict], core: dict[str, dict]) -> list[dict]:
    """Join each version with its core row. Order: core.csv order, then version a, b, c."""
    order = {cid: i for i, cid in enumerate(core)}
    records = []
    for v in variants:
        c = core.get(v["core_id"])
        if c is None:
            raise DatasetError(f"{v['core_id']}.{v['version']}: core_id not in core.csv")
        rec = {**c, **v, "id": f"{v['core_id']}.{v['version']}"}
        records.append({k: rec[k] for k in FIELDS})
    records.sort(key=lambda r: (order[r["core_id"]], r["version"]))
    ids = [r["id"] for r in records]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise DatasetError(f"duplicate version ids: {dupes}")
    return records


def to_jsonl(records: list[dict]) -> bytes:
    lines = [json.dumps(r, ensure_ascii=False, separators=(", ", ": ")) for r in records]
    return ("\n".join(lines) + "\n").encode("utf-8")


def main() -> int:
    try:
        variants = parse_variants(VARIANTS_MD.read_text(encoding="utf-8"))
        records = build_records(variants, load_core(CORE_CSV))
    except DatasetError as e:
        print(f"build_dataset: {e}", file=sys.stderr)
        return 1
    data = to_jsonl(records)
    OUT_JSONL.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    OUT_VERSION.write_text(digest + "\n")
    print(f"wrote {len(records)} records to {OUT_JSONL.relative_to(ROOT)}; version {digest[:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
