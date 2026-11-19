# TL;DR

**What it is.** An eval that asks: when nobody mentions animals, does an AI model bring them up
anyway, where it matters?

**How it works.** 234 everyday requests (78 core requests, each written in 3 voices) where an
animal-friendly option exists but is not mentioned. Examples: a chicken-farm business plan, mice in the garage, a cheap wedding menu. Several
models answer each one. An LLM judge scores each answer 0–2 (see design.md), with flags for preachy
answers and for harm to pets. Cynthia hand-grades about 100 answers to check how well the judge
agrees with her.

**Why.** A model that never notices animals leaves out an option many users would want. A model
that lectures or refuses is not the goal either. The eval measures both.

**Who it's for.** A portfolio piece for a job application in AI evaluation and animal welfare. The
judge validation and an honest "what this does and doesn't measure" section matter more than size.

**Tools.** Inspect (`inspect_ai`), the UK AI Security Institute's eval library.
