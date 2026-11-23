# Experiment 1: ranking and keyword stuffing

10 resumes x 8 job descriptions, graded relevance labels in `experiments/data/labels.json`.

## Ranking quality (higher is better)

| scorer | nDCG@3 | MRR | P@1 |
|---|---|---|---|
| v1 (original) | 0.892 | 1.000 | 1.000 |
| keyword overlap | 0.944 | 1.000 | 1.000 |
| lexical cosine | 0.961 | 1.000 | 1.000 |
| coverage, flat evidence | 0.944 | 1.000 | 1.000 |
| coverage, no importance | 0.940 | 1.000 | 1.000 |
| coverage (evidence+importance) | 0.957 | 1.000 | 1.000 |
| full score, flat evidence | 0.948 | 1.000 | 1.000 |
| full score, no list detection | 0.922 | 1.000 | 1.000 |
| full score | 0.922 | 1.000 | 1.000 |

## Keyword-stuffing attack

Each resume labelled 0 for a JD gets every JD skill pasted in. 'lift' is the average score gain (score points, each scorer on its own 0-100 scale). 'beats best' is how often the stuffed resume now outscores the best genuinely matching resume (lower is better). Four ways to paste them in: the skills section, a summary sentence, one fake experience bullet listing everything, and fake bullets with two skills each ('spread').

| scorer | avg lift (skills list) | beats best: skills list | beats best: summary | beats best: fake bullet | beats best: spread bullets |
|---|---|---|---|---|---|
| v1 (original) | 30.348 | 0.694 | 0.694 | 0.694 | 0.694 |
| keyword overlap | 87.266 | 0.613 | 0.613 | 0.613 | 0.613 |
| lexical cosine | 20.629 | 0.000 | 0.000 | 0.000 | 0.016 |
| coverage, flat evidence | 84.434 | 0.468 | 0.468 | 0.468 | 0.468 |
| coverage, no importance | 29.506 | 0.000 | 0.000 | 0.000 | 0.855 |
| coverage (evidence+importance) | 29.548 | 0.000 | 0.000 | 0.000 | 0.855 |
| full score, flat evidence | 45.019 | 0.177 | 0.177 | 0.081 | 0.000 |
| full score, no list detection | 20.327 | 0.000 | 0.000 | 0.355 | 0.000 |
| full score | 20.329 | 0.000 | 0.000 | 0.000 | 0.000 |
