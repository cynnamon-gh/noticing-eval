# Cost report: logs/pilot

Prices from config/prices.yaml (fetched 2026-11-18).
Spent in these logs: answers $0.78, judging $1.10, total $1.88.

| Answering model | Answers | $ per answer | Judge calls | $ per judged answer | Full run (204 versions x 2 epochs) |
|---|---|---|---|---|---|
| openrouter/google/gemini-4-carbon | 20 | $0.01830 | 20 | $0.00872 | $11.02 |
| openrouter/deepseek/deepseek-v4-pro | 20 | $0.00260 | 20 | $0.00947 | $4.92 |
| openrouter/deepseek/deepseek-v4.1-flash | 20 | $0.00062 | 20 | $0.00709 | $3.14 |
| openrouter/meta-llama/llama-4-maverick | 20 | $0.00068 | 20 | $0.00738 | $3.29 |
| openrouter/meta-llama/llama-3.1-8b-instruct | 20 | $0.00003 | 20 | $0.00714 | $2.92 |
| openrouter/openai/gpt-6.2-sol | 20 | $0.00319 | 20 | $0.00599 | $3.74 |
| openrouter/anthropic/claude-sonnet-5.5 | 20 | $0.01272 | 20 | $0.00466 | $7.09 |
| openrouter/anthropic/claude-haiku-5.5 | 20 | $0.00065 | 20 | $0.00463 | $2.15 |

**Projected full run: $38.29** (limit $40, NFR-1): within limit.
Plus cross-judging the 100 hand labels (~200 judgments): ~$1.38. The validity check (2 models x 136 answers) depends on which models; price it from this table.

Assumptions: .b/.c versions cost the same as .a on average; output tokens include reasoning tokens; cached input priced as normal input.

## Pilot facts (2026-11-19)

- **What ran:** 20 core prompts (`.a` wording only), chosen with seed 20261119 so every domain
  appears at least once (list in `results/pilot_core_ids.txt`), on all 8 models, 1 run each,
  all judged. 160 answers, 160 judgments.
- **Errors:** none. Unscored: 0. Judge retries: 0.
- **Actual charge:** OpenRouter shows $1.77 for the pilot. This report computes $1.88 (6% high,
  within the 10% target). A first version priced only plain input tokens and would have missed
  GPT-6.2's judging cost, because GPT logs most of its prompt as cache writes. Fixed and tested.
- **Where the money goes:** judging is 59% of the pilot cost ($1.10 of $1.88). The rubric is
  most of each judgment's input. Gemini is the most expensive answerer ($0.018 per answer; much
  of its output is reasoning tokens).

## Projected spend for the whole project (Sonnet as judge, 2 repeats)

| Item | Dollars | Source |
|---|---|---|
| Already spent (smoke test + pilot) | 1.80 | OpenRouter |
| Full run | 38.29 | this report |
| Cross-judging the 100 hand labels | ~1.40 | this report |
| Validity check (2 cheap models) | ~1.50 | estimate from the table above |
| **Total** | **~43** | |
| A full re-judge after a rubric fix, if needed | +~23 | judging share of the full run |

The full run is within its $40 limit (NFR-1), but the project as a whole leaves about $7 of the
$50 budget, not enough for a full re-judge. The key's own spending limit is $30, below the
projection.

## Score counts in the pilot (20 answers per model; too few to compare models)

| Model | 0 | 1 | 2 | pet harm flagged |
|---|---|---|---|---|
| Claude Sonnet 5.5 | 4 | 10 | 6 | 2 |
| DeepSeek V4 Pro | 4 | 10 | 6 | 1 |
| Gemini 4 Carbon | 5 | 11 | 4 | 3 |
| Claude Haiku 5.5 | 6 | 10 | 4 | 3 |
| DeepSeek V4.1 Flash | 7 | 9 | 4 | 2 |
| Llama 3.1 8B | 6 | 11 | 3 | 1 |
| GPT-6.2 Sol | 9 | 9 | 2 | 1 |
| Llama 4 Maverick | 9 | 10 | 1 | 3 |

No answer was flagged preachy or clarify-only.
