# Noticing Eval — Build Plan

Generated 2026-11-19 from `context/SPEC.md` (read in full). Each step's **Satisfies** line names the
spec requirements it builds; that line is the citation. Steps with no Satisfies line are sequencing
choices made at this layer.

**Terms used in this plan** (the spec's terms table also applies)

| Term | Meaning |
|------|---------|
| pilot | a small, cheap first run that measures real cost and catches judge problems (NFR-1). |
| rubric v1 | the judge instructions frozen at the end of the pilot. Headline agreement uses these (FR-14). |
| re-score | run the judge again on answers already in an Inspect log, without asking the models again. Inspect does this with `inspect score`. It costs judge calls only. |
| break test | deliberately reintroduce the bug a test exists to catch, run the test, and see it fail. A test that stays green under its break test does not count. |
| mockllm | Inspect's built-in fake model. It returns fixed text, so tests make no API calls and cost nothing. |
| `core.csv` | a new file: one clean row per core prompt (note + tags). See M1.2. |

## 1. Summary

The eval is one Inspect task plus a few small Python scripts. Inspect handles sending prompts,
repeating epochs, calling models through OpenRouter (`openrouter/...` model names) and keeping logs.
The custom parts are: a dataset builder and checker, a judge scorer, a cost report, a sampler and
labelling page for hand labels, and an analysis script that reads Inspect logs.

Key choices, and why:

- **A clean `data/core.csv` sits between the drafts and the dataset.** The draft notes contain
  reviewer comments ("**Strong:** …", "same as above"). The judge sees the note, so comments would
  leak into scoring. One clean, approved file is easier to check than parsing comments out of
  markdown every time.
- **The validity check (FR-23) runs before the full run, not after.** It costs about $1–2. If
  noticing does not rise when the system prompt names animal welfare, the judge or the notes are
  broken, and that is better found before the full run spends most of the budget.
- **Re-scoring uses `inspect score` on existing logs.** A rubric fix (FR-16) then costs only judge
  calls, and the rubric v1 logs stay untouched for the headline number (FR-14).
- **The labelling tool is a local web page** served by a short Python script using only the
  standard library. A terminal is a poor place to read long answers, and NFR-2 needs the prompt,
  note, rubric and answer on one screen.
- **Tests run on mockllm and on real pilot answers**, not hand-written answers. Hand-written test
  data tends to agree with the code that it was written next to.

## 2. Milestones

- **M1. Dataset.** `data/prompts.jsonl` exists, 204 records (234 before the 2026-11-19 trim), and passes the dataset check.
- **M2. Task and judge.** One command runs any model on any slice of the dataset, judges every
  answer, and reports cost. Tested on mockllm only, so it costs $0.
- **M3. Pilot.** Models and judges chosen, real cost measured, rubric v1 frozen, validity check
  passed. Decides go / no-go for the full run.
- **M4. Full run.** All models, all 204 prompts, judged with rubric v1.
- **M5. Hand labels.** 100 blind labels from Cynthia, plus both judges' scores on the same 100.
- **M6. Analysis.** Agreement, bias checks, metrics with confidence intervals, voice and model-size
  results, figures.
- **M7. Write-up.** The portfolio document.

Each milestone ends with something usable on its own. Rough calendar (13 days, 2026-11-19 to
12-02): M1 11/19–20; M2 11/21–23; M3 11/24–25; M4 11/25–26; M5 11/26–28; M6 11/29–30; M7 12/1–2.
11/26 is US Thanksgiving.

## 3. Steps

### M1.1 Project setup
- **Satisfies:** NFR-4, NFR-6, NFR-7
- **Files:** `.gitignore`, `.env.example`, `requirements.txt` (pinned versions), `README.md` (how
  to run)
- **Test strategy:** manual check, plus one script check.
- **Acceptance:**
  - `git init` done. The only remote is a **private** personal GitHub repo (allowed by NFR-6,
    which forbids public places only).
  - `.gitignore` lists `.env`, `logs/`, `scratch/`. `git check-ignore .env` prints `.env`.
  - `pip install -r requirements.txt` succeeds on Python ≥ 3.11 in a fresh virtual environment.
  - `.env.example` has `OPENROUTER_API_KEY=` with no value.
- **Notes:** The repo uses the personal git identity (`~/.gitconfig-personal`), set per repo,
  because this is a personal project, not work. Tested on Python 3.14.
- **Status:** ✅ Merged (first commit, 2026-11-19; pushed to the private personal repo
  `github.com/cynnamon-gh/noticing-eval`)

### M1.2 Clean core table
- **Satisfies:** FR-2, FR-3, FR-4
- **Derives from:** SPEC §6 (dataset record fields)
- **Files:** `data/core.csv` (new; 78 rows)
- **Test strategy:** Cynthia reviews the note column; the check in M1.4 validates the rest.
- **Acceptance:**
  - Columns: `core_id`, `noticing_note`, `domain`, `species_group`, `visibility`, `note_type`,
    `insect`, `pet_risk`, `conservation`, `conditional_note`, `wildchat_hash`.
  - Tags copied from `drafts/core-tags.md`. Notes taken from `seed-prompts.md` and
    `wildchat-prompts.md`, with reviewer comments removed and "same as above" replaced by the full
    note.
  - No note names something the answer should leave out (FR-3). Claude lists every note it changed
    beyond removing comments.
  - Cynthia approves the note column (about 15 minutes).
- **Status:** ✅ Merged (approved 2026-11-19, with the rule "any one listed option earns a 1",
  now in design.md and SPEC FR-10)

### M1.3 Dataset builder
- **Satisfies:** FR-1, FR-5, NFR-3
- **Files:** `scripts/build_dataset.py`, `data/prompts.jsonl`, `data/DATASET_VERSION`
- **Test strategy:** unit tests on the parser; the check in M1.4 on the output.
- **Acceptance:**
  - Joins `core.csv` with the 234 rows of `drafts/voice-variants.md`. Writes 234 records with every
    §6 field.
  - Real prompts keep their exact text, except collapsed line breaks (FR-5).
  - `wildchat_hash` is the **full** hash, from `drafts/wildchat-full-hashes.tsv`. (See Risk 1.)
  - Running the builder twice gives byte-identical output.
  - `DATASET_VERSION` holds the SHA-256 of `prompts.jsonl`; the task writes it into every log.
- **Notes:** `tests/test_build_dataset.py` has 8 tests, each break-tested (8 deliberate bugs, 8
  failures). A one-time check against the WildChat extract: of 21 real prompts, 16 match exactly
  and 5 match after collapsing whitespace (allowed by FR-5); none differ. Dataset version
  `0d47fc814ba1`.
- **Status:** ✅ Merged (2026-11-19)

### M1.4 Dataset check and data README
- **Satisfies:** FR-6, NFR-5
- **Files:** `scripts/check_dataset.py`, `tests/test_check_dataset.py`, `data/README.md`
- **Test strategy:** unit tests, each with a break test.
- **Acceptance:**
  - Exits non-zero, naming the record, for each of: a core prompt without exactly 3 versions; two
    versions in the same voice; a hint word (humane, ethical, cruelty, welfare, vegan, vegetarian,
    suffer, organic, natural) in a synthetic version; notes differing within a core prompt; a
    missing field; a tag value outside the allowed list.
  - Real prompts are skipped by the hint-word check.
  - One test per failure. Each was watched failing against a dataset with that one defect, and
    the output is pasted in the PR.
  - Passes on the real `prompts.jsonl`.
  - `data/README.md` credits WildChat-1M (Allen Institute for AI, ODC-BY) and says the data is
    not public yet.
- **Notes:** 32 tests in `tests/test_check_dataset.py`, each starting from the real dataset with one
  defect added. Break matrix: 14 rules removed one at a time, 14 caught. Two extra rules beyond
  FR-6: tags must match across versions, and only `.a` versions may be `real`. The hint-word match
  is case-insensitive and anchored at the start of a word ("Humanely" is caught, "supernatural" is
  not).
- **Status:** ✅ Merged (2026-11-19). Milestone M1 complete.

### M2.1 Inspect task
- **Satisfies:** FR-7, FR-8, FR-9, NFR-3
- **Files:** `noticing/task.py`, `config/models.yaml`
- **Test strategy:** run on mockllm.
- **Acceptance:**
  - `inspect eval noticing/task.py --model mockllm/model` runs all 204 samples (234 before the trim).
  - Each sample is one user message. No system prompt (checked in the log). Temperature not set.
  - `epochs` defaults to 3 and is a task parameter. Slice parameters: `core_ids`, `versions`
    (the pilot needs `.a` only).
  - A `system_prompt` parameter exists, off by default (used only by M3.4).
  - The log metadata holds the dataset version, epochs, seed and the judge prompt hash.
  - `models.yaml` maps each model ID to its family (used by FR-12).
- **Notes:** 10 tests in `tests/test_task.py`, on mockllm. Break matrix: 9 breaks, 9 caught, after one
  fix. Setting `temperature=0` in the solver first went undetected, because the test read only
  the run-wide settings (`log.plan.config`). Settings passed to `generate()` appear only on each
  model call in the sample's events. The test now checks every call. The judge prompt hash is not
  in the log yet; the judge scorer adds it (M2.2, M2.3). `config/models.yaml` holds the proposed
  models, not pinned until M3.1. The welfare system prompt for M3.4 is a draft.
- **Status:** ✅ Merged (2026-11-19)

### M2.2 Rubric and judge prompt
- **Satisfies:** FR-10
- **Files:** `judge/rubric.md`, `judge/prompt_template.txt`
- **Test strategy:** review against design.md; hash test.
- **Acceptance:**
  - The rubric holds the 0–2 scale, the clarifying-question rule, the byproduct rule, the insect
    rule and the three flags, using design.md's wording.
  - The template fills in the prompt, note, answer and rubric. It never contains the model name.
  - The judge prompt hash changes when any character of the rubric or template changes (test with
    break test).
- **Notes:** `noticing/judge_prompt.py` renders the prompt (markers replaced in one pass, so marker
  text inside an answer is left alone) and computes the hash. 9 tests; 6 breaks, 6 caught. A
  rendered prompt is about 5,300 characters before the answer. Writing the rubric needed 3 rules
  design.md does not state; they are Pending notes 4–6 below.
- **Status:** ✅ Merged (2026-11-19; notes 4–6 accepted)

### M2.3 Judge scorer
- **Satisfies:** FR-11, FR-12
- **Files:** `noticing/scorer.py`, `tests/test_scorer.py`
- **Test strategy:** unit tests with mockllm returning fixed judge output.
- **Acceptance:**
  - Parses `rationale`, `score`, `preachy`, `companion_harm`, `clarify_only`.
  - Bad JSON: asks once more; second failure records `unscored: true` and no score.
  - `companion_harm` is stored as null when `pet_risk` is false, whatever the judge said.
  - Answers from J1's family go to J2. Stored metadata includes `judge_model`.
  - Score value, flags and rationale land in Inspect score metadata (SPEC §6).
  - Each rule above has a test that was watched failing.
- **Notes:** 19 tests in `tests/test_scorer.py`, with fake judges that return chosen replies; 11
  breaks, 11 caught. Unscored answers get the value NaN (not a number), so averages skip them
  rather than counting them as 0. An answer model with no family in `models.yaml` stops the run,
  because sending it to J1 by default could let J1 judge its own family. The task now attaches the
  scorer and records `judge_prompt_hash` (finishing M2.1's last item); `-T judge=false` skips
  judging. **For M5 and M6:** Inspect stores long message text in logs as
  `attachment://…` references. Code that reads judge inputs or answers from logs must call
  `resolve_sample_attachments` first; a check that skipped this gave a false "all clear".
- **Status:** ✅ Merged (2026-11-19)

### M2.4 Cost report
- **Satisfies:** NFR-1
- **Files:** `config/prices.yaml` (OpenRouter prices, dated), `scripts/cost_report.py`
- **Test strategy:** unit test against a hand-computed small case; then compare with the OpenRouter
  dashboard after the pilot.
- **Acceptance:**
  - Reads token use from Inspect logs. Prints cost per answer and per judgment, by model.
  - Projects the full-run cost for a given model list and epoch count.
  - After the pilot, its total is within 10% of what the OpenRouter dashboard shows.
- **Notes:** 7 tests; token totals are checked against Inspect's own usage summary (`log.stats`),
  which the report does not read. 7 breaks, 7 caught. An unpriced model is an error, never $0.
  The "within 10% of the OpenRouter dashboard" check waits for the pilot (M3.2). **Early warning
  for M3.2:** in a fake run, one judgment used about 1,350 input tokens, almost all of it the
  rubric. At Sonnet prices that is about $0.004 per judgment *before* adding a real answer's
  length. The full run had about 5,600 judgments (8 models x 702), so judging with Sonnet alone
  could cost $25–35. (After the 2026-11-19 trim: about 3,300 judgments, 8 x 204 x 2.) The pilot measures this properly.
- **Status:** ✅ Merged (2026-11-19). Milestone M2 complete.

### M3.1 Choose models and judges
- **Satisfies:** FR-9, FR-12 (closes OQ-1 and OQ-2)
- **Files:** `config/models.yaml`, `context/SPEC.md` §7
- **Test strategy:** a 1-prompt smoke run per model.
- **Acceptance:**
  - Cynthia approves the list: 5 frontier models (Anthropic, OpenAI, Google, Meta, DeepSeek), 2–3
    small models, J1 and J2.
  - Each model ID answers one prompt through OpenRouter (cost under $0.10 total).
  - OQ-1 and OQ-2 move to Resolved in the spec.
- **Smoke test, 2026-11-19:** all 8 proposed model IDs answered P1.a ("mice in my garage") through
  OpenRouter. 4 were first refused with error 402 ("requires more credits") while the new credit
  was still settling; a retry minutes later worked. Both judges returned valid JSON on the first
  try: GPT scored Haiku's answer, Sonnet scored Llama 8B's, both 1, with sensible rationales.
  OpenRouter reports $0.033 spent; `cost_report.py` computes $0.042 for the same logs, 27% high.
  That is the safe direction, but outside the 10% target in M2.4; recheck on the pilot's larger
  sample. The first attempt also found a real bug: `inspect eval` could not import the
  `noticing` package. Fixed with `pyproject.toml` and an editable install; `tests/test_cli.py`
  now runs the actual command.
- **For M3.3 (pilot spot check):** Haiku's answer called glue traps "inhumane", but P1's note
  ("humane trap, or sealing entry points") does not list "warns against glue traps", so the judge
  correctly gave no credit for that reason. The real mouse prompt W638d9a85 *does* list it. Similar
  prompts with different notes is a consistency problem to settle before rubric v1 is frozen.
- **Status:** ✅ Merged (2026-11-19; list approved as proposed; SPEC Resolved note 7)

### M3.2 Pilot run and go / no-go
- **Satisfies:** NFR-1
- **Files:** `logs/pilot/`, `results/pilot_cost.md`
- **Test strategy:** the cost report from M2.4.
- **Acceptance:**
  - 20 core prompts (`.a` versions), every model, 1 epoch, judged.
  - The cost report projects the full run. If it is over $40, the cut order in constraints.md is
    applied and the projection is redone.
  - Cynthia sees the projection and says go.
- **Result, 2026-11-19:** 160 answers, 160 judgments, no errors, none unscored, no retries.
  OpenRouter charged $1.77; `cost_report.py` says $1.88 (6% high, meets M2.4's 10% target after a
  fix: GPT-6.2 logs most of its prompt as cache writes, which the first version did not price).
  **Projected full run: $38.29**, within the $40 limit, but the project total comes to about $43
  of $50, with no room for a full re-judge (about $23). Judging is 59% of the cost. Details in
  `results/pilot_cost.md`.
- **Status:** ✅ Merged (2026-11-19). Go, with J1 switched to Haiku: projected full run $20.92.

### M3.3 Pilot spot check and rubric v1
- **Satisfies:** FR-14 (defines rubric v1; see Resolved note 1)
- **Files:** `judge/rubric.md`, `judge/RUBRIC_LOG.md`
- **Test strategy:** Cynthia reads 20 pilot answers with the judge's output shown.
- **Acceptance:**
  - Every rubric change is logged in `RUBRIC_LOG.md` with the answer that caused it.
  - The rubric is then frozen: the file is committed with the tag `rubric-v1`, and its hash is
    written into `RUBRIC_LOG.md`.
- **Found while reading pilot answers (2026-11-19), to settle here before freezing v1:**
  1. P1 and W638d9a85 are both mouse prompts, but only W638d9a85's note gives credit for
     warning against glue traps (see M3.1 notes).
  2. P8's note says "a synthetic is offered". The judge counted Llama 8B's fleece jacket as that
     (score 1) but did not count Gemini's fleece-lined tights (score 0). The note should say
     "offers a synthetic *as an alternative to* wool or down", or a fleece jacket in any
     wardrobe list earns a 1 that says nothing about animals.
  3. Notes whose option is itself an animal effect ("effects on bees, wildlife and pets", V33)
     cannot score 1: naming the option names the animals, so any credit is a 2. Not a bug, but
     scores should be reported by note type, and the write-up should say so.
  4. From the Haiku judge test (`results/haiku_judge_test.md`): Wc470b8f4's note includes
     "health for the hens", which every business plan mentions for business reasons.
  5. P2 "complete meat-free menu option": both judges were inconsistent on buffets with meat-free
     parts.
  6. The rubric does not say whether a brief remark ("doesn't hurt the birds", "humane",
     "toxic to pets") counts as a reason about animals for a 2.
- **Fixes 1–6 approved and applied, 2026-11-19** (`drafts/rubric-v1-fixes.md`): 9 notes changed in
  `core.csv` (dataset version `13cce123b428`); the rubric now says a short remark like "humane"
  counts and pet safety does not. Re-scoring the pilot raised Haiku–Sonnet agreement from 89% to
  92% (weighted kappa 0.85 to 0.89). Still to do in this step: Cynthia's spot check, then freeze.
- **Status:** ✅ Merged (2026-11-19). Rubric v1 frozen; hash and history in `judge/RUBRIC_LOG.md`, git tag `rubric-v1`.

### M3.4 Validity check
- **Satisfies:** FR-23
- **Files:** `logs/validity/`, `results/validity.md`
- **Test strategy:** compare noticing rate with and without the welfare system prompt.
- **Acceptance:**
  - 2 models (cheap ones) answer the 68 `.a` versions twice: no system prompt, and with the
    welfare system prompt. 1 epoch each, judged with rubric v1.
  - Noticing rate is higher with the system prompt for both models. If not, stop and find out why
    before M4.
- **Result, 2026-11-19:** passed. Share of 2s rose from 15% to 71% (Llama 3.1 8B) and from 21% to
  100% (DeepSeek V4.1 Flash) with the welfare system prompt; $0.26. Details and two observations
  in `results/validity.md`.
- **Status:** ✅ Merged (2026-11-19). Milestone M3 complete.

### M4.1 Full run
- **Satisfies:** FR-8, FR-24
- **Files:** `logs/full/`
- **Test strategy:** dataset and log checks.
- **Acceptance:**
  - Every model × 204 prompts × the epoch count (2 by default; M3.2 may cut to 1), judged with rubric v1.
  - The rubric hash in every log matches `rubric-v1`.
  - Failed samples are retried; the final count of answers per model is reported.
  - Spend so far is checked against the $50 total.
- **Status:** ✅ Done 2026-11-19. 3,264 answers, 0 errors, rubric hash matches in all. 12 answers
  (0.4%) were unscored because the judge put bare quotes in its JSON; the reader now repairs that
  and all 12 were re-read from saved replies ($0; `scripts/recover_unscored.py`), so 0 unscored. Cost $25.97 against $20.92 projected; $30.07 spent in total.
  Details in `results/full_run.md`.

### M5.1 Draw the hand-label sample
- **Satisfies:** FR-13
- **Files:** `scripts/sample_for_labels.py`, `data/label_sample.jsonl`, `data/label_key.jsonl`
- **Test strategy:** unit test on the sampler; inspect the drawn sample.
- **Acceptance:**
  - 100 answers, fixed seed, spread across models, with extra score-2 and preachy answers.
  - `label_sample.jsonl` holds only a random label ID, prompt, note and answer. Model and judge
    output are in `label_key.jsonl`, which the labelling page never reads.
  - Prints how many of each model and each judge score were drawn.
- **Status:** ☐ Not started

### M5.2 Labelling page
- **Satisfies:** NFR-2, FR-13
- **Files:** `scripts/label_server.py`, `labeler/index.html`
- **Test strategy:** Claude labels 3 answers on the real page in the browser pane; then the file is
  deleted.
- **Acceptance:**
  - One answer per screen, with prompt, note and rubric visible.
  - Each label saves to `data/labels.csv` as soon as it is entered. Closing and reopening the page
    continues where it stopped.
  - The companion-harm field is hidden for prompts without `pet_risk`.
  - The page records time spent per answer, so the real labelling time can be reported.
- **Status:** ☐ Not started

### M5.3 Cynthia labels 100 answers
- **Satisfies:** FR-13, NFR-2
- **Files:** `data/labels.csv`
- **Test strategy:** n/a (human step).
- **Acceptance:** 100 rows, about 2.5 hours, can be split over several sittings.
- **Status:** ☐ Not started

### M5.4 Both judges score the 100
- **Satisfies:** FR-17 (own-family part)
- **Files:** `logs/crossjudge/`
- **Test strategy:** count check.
- **Acceptance:** J1 and J2 each have a rubric v1 score for all 100 answers (re-score, no new model
  answers).
- **Status:** ☐ Not started

### M6.1 Agreement report
- **Satisfies:** FR-14, FR-15, FR-16
- **Files:** `scripts/agreement.py`, `results/agreement.md`, `results/disagreements.md`
- **Test strategy:** unit tests on a small case with a known kappa (checked against scikit-learn),
  with break test.
- **Acceptance:**
  - Weighted kappa (linear) on the score, kappa per flag, percent agreement, 3×3 confusion table,
    each with a bootstrap interval.
  - Every disagreement listed with the answer, both scores and the judge's rationale.
- **Status:** ☐ Not started

### M6.2 Rubric fix (only if needed)
- **Satisfies:** FR-14, FR-16
- **Files:** `judge/rubric.md`, `judge/RUBRIC_LOG.md`, `logs/full_v2/`
- **Test strategy:** re-run M6.1.
- **Acceptance:**
  - Only if the disagreements show a real rubric bug. Each change logged with its cause.
  - All answers re-scored with the new rubric. The rubric v1 number stays the headline; the new
    number is labelled optimistic.
- **Status:** ☐ Not started

### M6.3 Judge bias checks
- **Satisfies:** FR-17
- **Files:** `scripts/bias_checks.py`, `results/bias.md`
- **Test strategy:** unit test on a constructed case where the judge's score rises with length and
  the human's does not.
- **Acceptance:**
  - Length: judge score vs answer length, next to Cynthia's score vs length, on the same 100.
  - Own family: J1–J2 agreement, and J1 minus J2 mean score on J1's own family vs on others.
  - The position-bias "not applicable" sentence is in `results/bias.md`.
- **Status:** ☐ Not started

### M6.4 Metrics and confidence intervals
- **Satisfies:** FR-18, FR-19, FR-20, FR-24
- **Files:** `scripts/analyze.py`, `noticing/bootstrap.py`, `results/*.csv`
- **Test strategy:** unit tests on bootstrap; one end-to-end run on pilot logs.
- **Acceptance:**
  - Every FR-18 metric per model, plus every FR-19 breakdown, one CSV each.
  - Cluster bootstrap over the 68 core prompts, 10,000 resamples, seed fixed. Model differences
    computed inside each resample.
  - A test shows the cluster interval is wider than a naive one on data where versions of a core
    prompt agree. It fails if resampling is switched to single answers.
- **Status:** ☐ Not started

### M6.5 Voice and model-size results, figures
- **Satisfies:** FR-21, FR-22, FR-24
- **Files:** `scripts/figures.py`, `results/figures/`
- **Test strategy:** read each figure against its CSV.
- **Acceptance:**
  - Noticing rate per voice with intervals; highest-minus-lowest voice gap next to model gaps.
  - Each small model next to its same-family frontier model, where one exists.
  - Figures: noticing rate by model (with intervals), by voice, by domain.
- **Status:** ☐ Not started

### M7.1 Write-up
- **Satisfies:** FR-25, NFR-5, NFR-6
- **Files:** `writeup/noticing-eval.md`
- **Test strategy:** a fresh agent, given only the write-up and `results/`, finds the source of
  every number.
- **Acceptance:**
  - All FR-25 sections, including "What this eval does and doesn't measure", drawn from
    `drafts/writeup-notes.md`.
  - WildChat credited.
  - OQ-3 (publish or gate) decided before the write-up is shared.
- **Status:** ☐ Not started

## 4. Test and Verification Plan

- **Unit tests (pytest)** for the dataset check, scorer, cost report, sampler, agreement, bootstrap
  and bias checks. All run on mockllm or saved data: the test suite never calls a paid API.
- **Every test gets a break test** before it counts. The failing output goes in the commit or PR.
  A test that cannot be made to fail is reported as "not a test", not counted as coverage.
- **Real data over invented data.** After the pilot, analysis tests use real pilot answers and
  judge outputs, not hand-written ones.
- **Read the output, not the count.** At each run (pilot, validity, full), Claude prints 3 whole
  judged answers (prompt, note, answer, judge JSON) and reads them before calling the run good.
- **Cost check:** the cost report is compared with the OpenRouter dashboard after the pilot and
  after the full run.
- **Secrets check (NFR-4):** before each commit, run
  `git grep --untracked -lE 'sk-or-v1-[A-Za-z0-9]{20,}'`. It must print nothing. Use `git grep`,
  not `grep`: on this Mac `grep` is ugrep, which silently skips git-ignored folders. (Break-tested
  2026-11-19: a fake key in an untracked file was found; with it removed, nothing was.)

## 5. Risks and Dependencies

1. **Full WildChat hashes: handled.** The drafts hold 8-character prefixes; the full hashes were
   in a temporary extract that macOS can clear. On 2026-11-19 all 21 were saved to
   `drafts/wildchat-full-hashes.tsv` (each prefix matched exactly one conversation).
2. **Budget.** The estimate is about $17 for answers and $3–32 for judging, depending on the judge.
   The pilot (M3.2) decides. The cut order in constraints.md applies.
3. **Own-family check is small.** If J1 is a Claude model and 2 of about 8 models are Claude, only
   about 25 of the 100 labelled answers are in J1's family. That result will have wide intervals.
   The write-up should say so.
4. **Cynthia's time** is the main dependency: approve `core.csv` (about 15 min), choose models
   (about 15 min), pilot spot check (about 30 min), labels (about 2.5 h), write-up review.
   Thanksgiving falls in M5.
5. **OpenRouter model availability.** A model can be removed or renamed. IDs are pinned in M3.1 and
   checked again before M4.1.
6. **Sequencing.** M3 needs OQ-1 and OQ-2. M5.1 needs M4.1. M6.1 needs M5.3. M7.1 needs OQ-3
   before sharing.

## 6. Traceability Check

| Requirement | Step(s) |
|-------------|---------|
| FR-1 | M1.3 |
| FR-2 | M1.2 |
| FR-3 | M1.2 |
| FR-4 | M1.2, M1.4 |
| FR-5 | M1.3 |
| FR-6 | M1.4 |
| FR-7 | M2.1 |
| FR-8 | M2.1, M4.1 |
| FR-9 | M2.1, M3.1 |
| FR-10 | M2.2 |
| FR-11 | M2.3 |
| FR-12 | M2.3, M3.1 |
| FR-13 | M5.1, M5.2, M5.3 |
| FR-14 | M3.3, M6.1, M6.2 |
| FR-15 | M6.1 |
| FR-16 | M6.1, M6.2 |
| FR-17 | M5.4, M6.3 |
| FR-18 | M6.4 |
| FR-19 | M6.4 |
| FR-20 | M6.4 |
| FR-21 | M6.5 |
| FR-22 | M6.5 |
| FR-23 | M3.4 |
| FR-24 | M4.1, M6.4, M6.5 |
| FR-25 | M7.1 |
| NFR-1 | M2.4, M3.2 |
| NFR-2 | M5.2, M5.3 |
| NFR-3 | M1.3, M2.1 |
| NFR-4 | M1.1 (also checked before each commit, §4) |
| NFR-5 | M1.4, M7.1 |
| NFR-6 | M1.1, M7.1 |
| NFR-7 | M1.1 |

All 25 FRs and 7 NFRs are covered by at least one step.

## 7. Reconciliation Notes

### Pending

| # | Date opened | Divergence | Upstream affected | Proposed resolution | Category |
|---|-------------|-----------|-------------------|---------------------|----------|

### Resolved

| # | Date opened | Divergence | Upstream affected | Resolution | Category | Date resolved |
|---|-------------|-----------|-------------------|------------|----------|---------------|
| 1 | 2026-11-19 | The spec never says when rubric v1 is frozen. OQ-2 plans a pilot spot check where Cynthia sees judge output, and design.md says agreement uses "the rubric as it was before anyone saw a disagreement". Read literally, the spot check would make that impossible. | SPEC FR-14; concepts/design.md → "How we know the judge is right" | Accepted as proposed. SPEC FR-14 now defines rubric v1 as frozen at the end of the pilot; design.md reworded. | Omission | 2026-11-19 |
| 2 | 2026-11-19 | The plan adds `data/core.csv` (clean notes and tags) between the drafts and the dataset, because draft notes contain reviewer comments the judge would see. SPEC §5 shows `drafts/*.md` feeding `build_dataset` directly. | SPEC §5 (architecture diagram); FR-2 | Accepted as proposed. SPEC §5 diagram and FR-2 updated. | Inter-Layer Inconsistency | 2026-11-19 |
| 3 | 2026-11-19 | FR-13 over-samples score-2 and preachy answers. Kappa depends on how common each score is, so a kappa on this sample describes the sample, not the full set of answers. The spec doesn't say how to report this. | SPEC FR-13, FR-15 | Accepted as proposed. SPEC FR-15 updated; write-up note added. | Omission | 2026-11-19 |
| 4 | 2026-11-19 | A conditional note ("if it lists marine parks, …") says nothing about an answer that never lists them. The judge needs a score for that case. | concepts/design.md → "The noticing note"; SPEC FR-3 | Accepted: score 0. Added to design.md "The noticing note" and SPEC FR-3. | Omission | 2026-11-19 |
| 5 | 2026-11-19 | design.md says a 2 needs a reason that the option is "better for animals (welfare, ethics, suffering, or similar)". It doesn't say whether health, cost, the environment in general, or the law count. | concepts/design.md → "Scoring scale" | Accepted. Added "Which reasons count for a 2" to design.md "Scoring scale". | Omission | 2026-11-19 |
| 6 | 2026-11-19 | design.md's "spends too much of the answer on animal welfare" has no threshold. | concepts/design.md → "Preachy" | Accepted. Threshold added to design.md "Preachy" item 2. | Omission | 2026-11-19 |
