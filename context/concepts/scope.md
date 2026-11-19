# Scope

## In scope

- **Single-turn requests.** The model sees one user message and answers once. No follow-up turns.
- **English only.** Non-native English is one of the five voices, but every prompt is in English.
- **Text only.** No images, no tools, no agents.
- **68 core prompts × 3 voice versions = 204 prompts.** 51 core prompts are synthetic and 17 are
  real (WildChat). See `drafts/voice-variants.md`. (78 / 234 until 2026-11-19, when 10
  near-duplicate meat-free prompts were removed to save cost.)
- **About 8 models.** One current frontier model each from Anthropic, OpenAI, Google, Meta (Llama)
  and DeepSeek, plus 2–3 small or cheap models. The small models answer one extra question: does
  noticing grow with model size? (Decided 2026-11-18.)
- **One LLM judge**, swapped for a different-family judge when scoring answers from the judge's own
  family. (Decided 2026-11-18.)
- **Hand-labelling about 100 answers** by Cynthia, to measure how well the judge agrees with her.
- **A write-up** with a "What this eval does and doesn't measure" section. Notes are collected in
  `drafts/writeup-notes.md`.

## Out of scope

- **Multi-turn conversations and pressure tests.** MANTA covers these.
- **Agents and tool use.** TAC covers these.
- **Companion animals as the subject of the score.** Harm to them is a flag only. Pet fish are the
  exception (see design.md, "Which animals count").
- **Training or fine-tuning models.** This eval measures; it does not try to change behaviour.
- **Non-English prompts.**

## Success criteria

The project is done when all of these are true:

1. Every model has answered every prompt, and every answer has a judge score and flags.
2. Judge-vs-Cynthia agreement on about 100 answers is reported, with where they disagree and what
   changed in the rubric because of it.
3. Model comparisons carry confidence intervals, and no claim says "A beats B" when the interval
   says the gap could be noise.
4. The voice result is reported: does voice change noticing?
5. The write-up exists and includes the "does and doesn't measure" section.

## Phasing

1. **Pilot:** a small run to measure cost and catch judge problems before spending the budget.
2. **Full run** on all models.
3. **Hand-labelling and judge validation.** Fix the rubric if agreement is poor, then re-judge.
4. **Analysis and write-up.**
