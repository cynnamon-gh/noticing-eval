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

## Git

This is a personal project. The repo uses the personal git identity from `~/.gitconfig-personal`
(set with `git config --local include.path ~/.gitconfig-personal`), not the work one.

The remote is a **private** personal repo: `git@github.com:cynnamon-gh/noticing-eval.git` (pushed
with the personal SSH key). Keep it private: the prompt set must not go anywhere public until the
spec's Open Question 3 (publish openly, or gate it) is decided.

## Data credit

Some prompts come from WildChat-1M (Allen Institute for AI), used under the ODC-BY license.
