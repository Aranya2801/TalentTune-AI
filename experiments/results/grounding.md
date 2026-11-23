# Experiment 2: catching fabricated resume edits

10 resumes x 5 seeds. One edit per sample. An edit is 'flagged' when the checker reports at least one medium/high issue.

## Detection rate per fabrication type (higher is better)

| fabrication | n | numbers only | numbers + skills | + titles/names/bullets | all checks |
|---|---|---|---|---|---|
| added metric | 50 | 1.000 | 1.000 | 1.000 | 1.000 |
| inflated metric | 45 | 1.000 | 1.000 | 1.000 | 1.000 |
| skill copied from JD | 50 | 0.000 | 1.000 | 1.000 | 1.000 |
| title inflation | 50 | 0.000 | 0.000 | 1.000 | 1.000 |
| date shifted | 50 | 1.000 | 1.000 | 1.000 | 1.000 |
| employer renamed | 50 | 0.000 | 0.000 | 1.000 | 1.000 |
| invented bullet | 50 | 0.000 | 0.000 | 1.000 | 1.000 |
| **all fabrications** | 345 | 0.420 | 0.565 | 1.000 | 1.000 |

## Harder cases (added after the checker was written)

Written after the main checks, to find where they stop working. The scope check (leadership verbs) was added *because* of the first row, so that 0.90 is not a held-out number. The last column also counts low-severity notes, which the pipeline shows to the user but doesn't block on.

| fabrication | n | numbers only | numbers + skills | + titles/names/bullets | all checks | any issue incl. low |
|---|---|---|---|---|---|---|
| scope inflation (verb) | 50 | 0.000 | 0.000 | 0.000 | 0.900 | 0.900 |
| tacked-on claim | 50 | 0.000 | 0.000 | 0.000 | 0.000 | 0.340 |
| tool outside taxonomy | 50 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 |

## False alarm rate on faithful edits (lower is better)

| edit | n | numbers only | numbers + skills | + titles/names/bullets | all checks |
|---|---|---|---|---|---|
| rule-based rewrite | 50 | 0.000 | 0.000 | 0.000 | 0.000 |
| verb swaps | 50 | 0.000 | 0.000 | 0.000 | 0.000 |
| dropped a bullet | 50 | 0.000 | 0.000 | 0.000 | 0.000 |
| shuffled bullets | 50 | 0.000 | 0.000 | 0.000 | 0.000 |
| synonym paraphrase | 50 | 0.000 | 0.000 | 0.000 | 0.000 |
| merged two bullets | 50 | 0.000 | 0.000 | 0.000 | 0.000 |
| condensed a bullet | 50 | 0.000 | 0.000 | 0.000 | 0.000 |
| **all faithful edits** | 350 | 0.000 | 0.000 | 0.000 | 0.000 |

## Overall (main fabrication set vs faithful edits)

| detector | precision | recall | F1 |
|---|---|---|---|
| numbers only | 1.000 | 0.420 | 0.592 |
| numbers + skills | 1.000 | 0.565 | 0.722 |
| + titles/names/bullets | 1.000 | 1.000 | 1.000 |
| all checks | 1.000 | 1.000 | 1.000 |
