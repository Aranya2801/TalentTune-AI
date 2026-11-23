# Contributing

Issues and PRs are welcome. A few notes so they're easy to merge:

- Run `ruff check .` and `pytest` before pushing. Tests don't need network or an API key.
- If you change scoring or the fact-checker, rerun `python experiments/ranking.py`
  and `python experiments/grounding_eval.py` and commit the updated files in
  `experiments/results/` so the diff shows what moved.
- New skills go in `talenttune/data/skills.txt` (format is explained at the top of
  the file). Use a `=` alias for anything that is also a normal English word.
- New benchmark resumes/JDs are very welcome, please keep them fictional and add
  labels for every JD in `experiments/data/labels.json`.

Bug reports are most useful with the resume/JD text (anonymised) and the output of
`python -m talenttune score --json ...`.
