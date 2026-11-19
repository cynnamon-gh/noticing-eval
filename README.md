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
cp .env.example .env
```

Then open `.env` and paste your OpenRouter key after `OPENROUTER_API_KEY=`. Git ignores `.env`, so
the key is never committed.

## Build the dataset

```bash
.venv/bin/python scripts/build_dataset.py
.venv/bin/python -m pytest -q
```

The builder joins `data/core.csv` (one note and set of tags per core prompt) with the 234 wordings
in `drafts/voice-variants.md`, and writes `data/prompts.jsonl` plus `data/DATASET_VERSION` (its
SHA-256). Edit those two inputs, never `prompts.jsonl` by hand.

## Run the eval

```bash
.venv/bin/inspect eval noticing/task.py --model mockllm/model -T epochs=1   # fake model, $0
.venv/bin/inspect eval noticing/task.py --model openrouter/<model id>      # real model, costs money
```

Task options (`-T name=value`): `epochs` (default 3), `versions` (e.g. `a` for originals only),
`core_ids` (e.g. `P1,V20`), `welfare_system_prompt` (validity check only). Logs go to `logs/`.

## Git

This is a personal project. The repo uses the personal git identity from `~/.gitconfig-personal`
(set with `git config --local include.path ~/.gitconfig-personal`), not the work one.

The remote is a **private** personal repo: `git@github.com:cynnamon-gh/noticing-eval.git` (pushed
with the personal SSH key). Keep it private: the prompt set must not go anywhere public until the
spec's Open Question 3 (publish openly, or gate it) is decided.

## Data credit

Some prompts come from WildChat-1M (Allen Institute for AI), used under the ODC-BY license.
