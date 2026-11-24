# Noticing eval

Do AI models bring up animal welfare on their own, when an everyday request has an animal-friendly
option and the user doesn't mention animals? This repo holds the prompts, the Inspect eval, the
judge, and the analysis.

- What it measures and why: `context/concepts/tldr.md` and `context/concepts/design.md`
- Requirements: `context/SPEC.md`
- Build steps and status: `context/BUILD_PLAN.md`

## Setup

Needs Python 3.11 or later. Tested on 3.14.

```bash
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -r requirements.txt
uv pip install --python .venv/bin/python -e .   # makes `noticing` importable by the inspect command
cp .env.example .env
```

Then open `.env` and paste your OpenRouter key after `OPENROUTER_API_KEY=`. Git ignores `.env`, so
the key is never committed.

## Build the dataset

```bash
.venv/bin/python scripts/build_dataset.py
.venv/bin/python -m pytest -q
```

The builder joins `data/core.csv` (one note and set of tags per core prompt) with the 204 wordings
in `drafts/voice-variants.md`, and writes `data/prompts.jsonl` plus `data/DATASET_VERSION` (its
SHA-256). Edit those two inputs, never `prompts.jsonl` by hand.

## Run the eval

```bash
.venv/bin/inspect eval noticing/task.py --model mockllm/model -T epochs=1   # fake model, $0
.venv/bin/inspect eval noticing/task.py --model openrouter/<model id>      # real model, costs money
```

Task options (`-T name=value`): `epochs` (default 2), `versions` (e.g. `a` for originals only),
`core_ids` (e.g. `P1,V20`), `welfare_system_prompt` (validity check only), `judge` (`false` to skip
judging), `j1` / `j2` (judge models; default from `config/models.yaml`). Logs go to `logs/`.

After a run, check what it cost and what the full run would cost:

```bash
.venv/bin/python scripts/cost_report.py logs/pilot --epochs 2
```

Prices are in `config/prices.yaml`; a model missing from it stops the report.

Every answer is judged by J1, except answers from J1's own model family, which go to J2. A model
missing from `config/models.yaml` stops the run, because its family is unknown.

## Hand labels

Draw the 100 answers to label (fixed seed; writes `data/label_sample.jsonl` and
`data/label_key.jsonl`):

```bash
.venv/bin/python scripts/sample_for_labels.py logs/full
```

Start the labelling page, then open http://127.0.0.1:8790:

```bash
.venv/bin/python scripts/label_server.py
```

The page shows one answer at a time with the prompt, noticing note and rubric, and never the model
or the judge's score. Each label is written to `data/labels.csv` the moment it is saved, so you can
stop at any time; the page reopens at the first unlabelled answer. Keys: `0` `1` `2` score, Enter
save, arrows move. Port 8790 is used because 8765 is often taken; change it with `--port`.

## Git

This is a personal project. The repo uses the personal git identity from `~/.gitconfig-personal`
(set with `git config --local include.path ~/.gitconfig-personal`), not the work one.

The remote is a personal repo: `git@github.com:cynnamon-gh/noticing-eval.git` (pushed with the
personal SSH key). It is private for now. The prompt set may be published openly (decided
2026-11-20, SPEC Open Question 3); making the repo public is a separate step Cynthia takes when the
write-up is ready.

## Data credit

Some prompts come from WildChat-1M (Allen Institute for AI), used under the ODC-BY license.
