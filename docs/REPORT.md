# Evidence-weighted matching and fact-checked rewriting for resume tailoring

Notes on the design and the experiments behind TalentTune-AI v0.3.
Aranya Ghosh, November 2026.

## 1. Problem

Resume "optimisers" usually do two things: compute a match/ATS score between a
resume and a job description, and ask an LLM to rewrite the resume so that score goes
up. Both steps have a quiet failure mode.

- **The score rewards mentions, not experience.** Almost every keyword based score
  (including the one in v0.1 of this repo) counts a skill the same whether it appears
  in a bullet describing real work or in a pasted list. That makes the score trivially
  gameable, and it also makes it a bad target for an optimiser.
- **The optimiser optimises the score.** If the rewriter is told to raise keyword
  coverage, the cheapest way to do that is to write the missing keywords in. A "never
  fabricate" line in the prompt doesn't change the incentive. The v0.1 prompt asked for
  both at once.

The question this project tries to answer: *can a simple, explainable pipeline make
the score harder to game and the rewriter measurably less willing to invent things,
without giving up the improvement that tailoring actually brings?*

## 2. Method

### 2.1 Requirements from the JD

The JD is split into sections by header heuristics. Sections are mapped to an
importance weight: required 1.0, responsibilities 0.8, unlabelled text 0.6,
nice-to-have 0.4, benefits/company blurb 0 (dropped). Inline cues ("is a plus",
"ideally") move a single line to nice-to-have.

Skills are found with a hand-written taxonomy (~130 skills, ~290 aliases, a few
case-sensitive ones like `Go`, `React`, `REST` to avoid matching English words). Two
structural rules matter in practice:

- **OR-groups.** "Kafka or RabbitMQ" becomes one requirement satisfied by either.
- **Bracketed examples.** In "AWS (EC2, S3, Lambda)", the bracketed skills imply AWS
  in the taxonomy, so they're treated as examples and weighted ×0.6.

### 2.2 Evidence from the resume

Every line is tagged with its section and kind (bullet / role header / text). A skill
gets the maximum evidence over its mentions:

| where | evidence |
|---|---|
| experience bullet | 1.0 |
| experience text | 0.9 |
| project bullet | 0.85 |
| role / project header | 0.8 / 0.7 |
| summary | 0.45 |
| skills list | 0.35 |

Skills implied by a mentioned skill (FastAPI → Python) get half of its evidence. A
line with five or more skills where skill names make up at least half the characters
is treated as a list regardless of where it sits ("list detection").

### 2.3 Score

Coverage is `Σ importance · evidence / Σ importance` over requirements. The final
score adds lexical similarity (sublinear-tf cosine, rescaled by 0.5, the typical
value for a good fit on our data), share of bullets with a metric, share of bullets
with a strong opener, a structure checklist, and a years-of-experience ratio. Weights
are 0.45 / 0.15 / 0.15 / 0.10 / 0.10 / 0.05. They were set by hand and not tuned on
the benchmark.

### 2.4 Fact-checker

Given the original resume and a rewrite, each line of the rewrite is checked for:

| check | severity |
|---|---|
| number not in the original | high |
| number in the original but in an unrelated line (role headers must match the same role) | high |
| title gained a seniority word (senior, lead, principal, ...) | high |
| skill not in the original (or implied by it) | medium |
| bullet now opens with a leadership verb (led, spearheaded, managed...) the source line doesn't support | medium |
| bullet with < 34% term overlap with any original line and < 50% with the whole resume | medium |
| new proper noun in a role header (employer/school changed) | medium |
| new proper noun elsewhere | low |

"Related line" means sharing at least two content terms and at least 30% of the
shorter line. Faithfulness is `100 − 15·high − 7·medium − 2·low`.

### 2.5 Pipeline

```
score(original) → LLM rewrite (allowed skills + explicit gap list in the prompt)
               → check → if high/medium issues: one repair prompt with the issues
               → check → still failing: revert flagged lines to the closest original line
               → score(final)
```

Gaps and missing metrics are returned to the user as suggestions. Without an API key
a rule-based rewriter is used: it swaps weak openers ("worked on" → "developed"),
orders bullets and skills by JD relevance, and adds nothing.

## 3. Data

10 resumes and 8 JDs written for this project (backend Python, backend Java, ML,
data analyst, frontend, SRE, data engineer, Android, plus a junior full-stack resume
with an inflated skills list and a data scientist). Relevance labels 0/1/2 for each of
the 80 pairs were assigned by hand. All names and companies are fictional.

This is small. It's enough to show the stuffing effect clearly and to exercise the
checker, not to make claims about ranking quality in general.

## 4. Results

### 4.1 Ranking and stuffing (`experiments/results/ranking.md`)

On clean data the task is easy: every scorer, including plain keyword overlap, puts
the right resume first for all 8 JDs (P@1 = 1.0, MRR = 1.0). nDCG@3 ranges from 0.89
(v1) to 0.96 (lexical cosine, evidence coverage). The full score is at 0.92; the
other components (metrics, verbs) shuffle ranks 2-3 a little.

Under attack the methods separate. 62 (JD, non-fitting resume) pairs; share where the
stuffed resume beats the best real match:

| scorer | skills list | summary sentence | one fake bullet | 2-skill fake bullets |
|---|---|---|---|---|
| v1 | 0.69 | 0.69 | 0.69 | 0.69 |
| keyword overlap | 0.61 | 0.61 | 0.61 | 0.61 |
| coverage, flat evidence | 0.47 | 0.47 | 0.47 | 0.47 |
| coverage, evidence weighted | 0.00 | 0.00 | 0.00 | 0.86 |
| full, no list detection | 0.00 | 0.00 | 0.35 | 0.00 |
| full | 0.00 | 0.00 | 0.00 | 0.00 |

Takeaways:

1. Evidence weighting removes the gain from list and summary stuffing.
2. List detection is what handles the single "Worked with A, B, C, D, E..." bullet
   (0.35 → 0).
3. Believable fake bullets defeat coverage completely (0.86). The full score survives
   them only through the metric and verb components, which an attacker can satisfy too.
   No text-only method can tell a well-written lie from experience.
4. Lexical cosine alone is surprisingly robust to stuffing (pasting skills makes the
   resume longer and the cosine barely moves), but it can't say *which* requirement is
   missing, so it's a signal rather than a report.

### 4.2 Fabrication detection (`experiments/results/grounding.md`)

345 fabricated edits (added metric, inflated metric, skill copied from the JD, title
inflation, shifted date, renamed employer, invented bullet) and 350 faithful edits.

| checks | precision | recall |
|---|---|---|
| numbers | 1.00 | 0.42 |
| + skills | 1.00 | 0.57 |
| + titles, names, bullet support | 1.00 | 1.00 |

The perfect score is partly by construction: the perturbations and the checks were
written by the same person. Two fixes came out of this experiment and are worth
mentioning because they were real bugs: numbers with units ("3TB") were not being
extracted at all, and a shifted year that happened to appear elsewhere in the resume
passed the check, which is why numbers are now matched per line and dates per role.

Cases written afterwards to probe the limits:

| fabrication | caught |
|---|---|
| "helped build" → "led" | 0.90 (check added after seeing this fail, not held out) |
| extra clause on a real bullet | 0.00 (0.34 with low-severity notes) |
| tool not in the taxonomy | 0.00 (1.00 as a low-severity note) |

### 4.3 LLM rewriting

`experiments/llm_tailoring.py` compares the v1 prompt, the new prompt without the
guard, and the guarded pipeline on the same pairs. It's in the repo and tested with a
scripted fake model, but results aren't committed yet: they depend on the model
version and cost money to reproduce.

## 5. Limitations and next steps

- Hand-written taxonomy; poor coverage outside tech roles. A learned skill extractor
  or ESCO/O*NET mapping would help.
- The checker can only compare against the original. It has no way of knowing if the
  original already exaggerates.
- "Tacked-on" claims are the biggest gap. A natural next step is an NLI model that
  checks each rewritten bullet is entailed by its source bullet(s).
- The benchmark needs to be bigger and labelled by more than one person.
