# Full run re-judged with rubric v2 (M6.2), 2026-11-19

All 3,264 full-run answers re-scored with rubric v2 (hash `6d9261a0…`; the "same plan" rule,
`drafts/rubric-v2-proposal.md`). No answers were generated: `inspect score` re-ran the judge on
the saved answers. Logs: `logs/full_v2/` (gitignored); the v1 logs in `logs/full/` are unchanged.

## Checks

| Check | Result |
|---|---|
| Logs | 8 of 8 `success`, 408 answers each |
| Answers identical to the v1 run | 3,264 of 3,264 |
| Rubric v2 hash on every score | 3,264 of 3,264 |
| Judge routing | Haiku for the 6 non-Anthropic models, GPT-6.2 for Sonnet and Haiku |
| Unscored | 0 |
| Cost | $7.85 (OpenRouter usage before and after). Estimated $5.90; 33% over, cause not found. The re-scored logs keep the old run's token counts, so the cost report cannot price this run. |

$0.53 is left on the key. The remaining steps (M6.3–M7) need no model calls.

## Score changes from v1 to v2

| Change | Answers |
|---|---|
| 1 → 0 | 135 |
| 2 → 1 | 71 |
| 1 → 2 | 33 |
| 0 → 1 | 31 |
| 2 → 0 | 5 |
| 0 → 2 | 2 |
| unchanged | 2,987 |

- **1 → 0 (135)** is mostly the new rule: a kind step inside a harmful plan no longer counts.
- **2 → 1 outnumbers 1 → 2 (71 vs 33).** The rule does not touch reasons, so a symmetric split
  would be run-to-run variation. The excess (38) points to the longer rubric making Haiku
  stricter about what counts as a reason about the animals. The hand-label tests showed the same
  direction (L092, L099). Concentrated in DeepSeek V4 Pro (18), DeepSeek V4.1 Flash (17) and
  Gemini 4 Carbon (19), all judged by Haiku; GPT-6.2 moved no 2 → 1 on Sonnet.

## Scores under v2

| Model | 0 | 1 | 2 |
|---|---|---|---|
| Claude Sonnet 5.5 | 106 | 153 | 149 |
| DeepSeek V4 Pro | 117 | 157 | 134 |
| Claude Haiku 5.5 | 130 | 149 | 129 |
| Gemini 4 Carbon | 116 | 175 | 117 |
| DeepSeek V4.1 Flash | 105 | 202 | 101 |
| Llama 4 Maverick | 165 | 174 | 69 |
| Llama 3.1 8B | 199 | 156 | 53 |
| GPT-6.2 Sol | 187 | 190 | 31 |

Not analysed yet (M6.4 adds intervals and comparisons). Sonnet and Haiku answers are judged by
GPT-6.2, the others by Haiku.
