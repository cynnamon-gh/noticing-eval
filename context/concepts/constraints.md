# Constraints

## Money

**Up to $50 in API costs for the whole project**: model answers, judge runs and reruns. (Decided
2026-11-18.)

This is tight for about 8 models × 204 prompts × several runs each, plus judging every answer. No
price has been checked yet. So the first run is a small pilot that measures the real cost per
answer and per judgment. The full run is sized from that measurement, not from a guess.

If the pilot shows the full run would cost too much, cut in this order:
1. fewer repeated runs per prompt (3 → 2). **Applied 2026-11-19**, together with removing 10
   near-duplicate meat-free prompts (78 → 68 core prompts), before the pilot.
2. fewer small models
3. a cheaper judge, but only if its agreement with Cynthia stays acceptable. **Applied 2026-11-19**:
   judge 1 is Claude Haiku instead of Sonnet, after it matched Sonnet on 89% of pilot answers.
   Its agreement with Cynthia is still measured on the 100 hand labels.

## Time

**Done within 2 weeks**, by about 2026-12-02. (Decided 2026-11-18.) This is for a job application.

Cynthia's own time is the scarcest part. Hand-labelling 100 answers takes roughly 2–3 hours
(estimate: about 1.5 minutes per answer, not measured).

## Accounts and keys

- Models are reached through **OpenRouter**, so one API key covers all providers.
- Keys live in a `.env` file that git ignores. They are never committed.

## Tools

- **Python** and **Inspect** (`inspect_ai`).
- The project runs on Cynthia's Mac.

## Data licensing

- WildChat prompts are reused under the ODC-BY license. The write-up and the dataset must credit
  the Allen Institute for AI.
- Whether to publish the prompt set openly is undecided. TAC gated its data so future models
  aren't trained on it.
