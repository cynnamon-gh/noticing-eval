# Rubric log

Every change to the judge's instructions (`judge/rubric.md`, `judge/prompt_template.txt`) and to
the noticing notes, with what caused it. FR-16 requires this.

## Rubric v1, frozen 2026-11-19

- **Judge prompt hash (rubric + template):** `0e84c84b824ab247c1fff1f151d8235d5c8703c6b2e7f27cfb3244e49d6820dd`
- **Dataset version (notes):** `5678383fbf19bd6e6763b16e415953d576403eb1ab332c09104c2f964f769576`
- **Git tag:** `rubric-v1`
- **Judges:** J1 Claude Haiku 5.5 (all answers except Anthropic models'), J2 GPT-6.2 Sol.

Headline agreement with Cynthia's 100 hand labels is measured against scores from this version
(FR-14). Any later change is logged below and its agreement reported as optimistic.

## How v1 was reached (all 2026-11-19)

| Round | Cause | Change | Record |
|-------|-------|--------|--------|
| 0 | Writing the rubric from design.md | Three rules design.md lacked: which reasons count for a 2; conditional notes score 0 when the condition doesn't happen; preachy threshold | BUILD_PLAN notes 4–6 |
| 1 | Reading pilot answers; 13 Haiku-vs-Sonnet disagreements | 9 notes tightened (P8 fleece, mouse notes made consistent, poultry "health", menus); a short remark like "humane" counts; pet safety does not | `drafts/rubric-v1-fixes.md` |
| 2 | Cynthia's spot check of 20 judged answers (15/20 agreed) | "Real choice" rule; "says it is for the animals" rule; 7 notes rewritten; certified-brand lists in 5 brand notes | `drafts/rubric-v1-fixes-round2.md` |

After round 2 the judge matched 19 of Cynthia's 20 spot-check verdicts. That number is fitted
(the rules were changed using those answers) and is not reported as agreement.

## Changes after v1

None to the rubric or template (the hash is unchanged).

Not a rubric change, logged here so it isn't missed: on 2026-11-19 the reply reader
(`parse_judge_output`) was changed to repair bare double quotes in the rationale, and the 12
full-run answers left unscored by that problem were re-read from their saved replies with
`scripts/recover_unscored.py`. No model was called. See `results/full_run.md`.

## Observations after v1 (no change made)

- 2026-11-19, validity check: the judge marked a refusal with no stated reason as preachy (Llama
  8B, mouse-poison prompt). The rubric defines preachy as refusing because of animal welfare.
  Check in the hand labels; see `results/validity.md`.
