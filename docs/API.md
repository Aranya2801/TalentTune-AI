# API

Start the server with `uvicorn talenttune.api.app:app --reload`. Interactive docs are
at `http://localhost:8000/docs`.

LLM features use `ANTHROPIC_API_KEY` from the environment, or an `X-Anthropic-Key`
header per request (that's what the web UI sends if you paste a key). Without a key,
`/tailor` uses the rule-based rewriter.

## `POST /api/v1/score`

```json
{ "resume_text": "...", "job_description": "..." }
```

Returns the match report:

```json
{
  "score": 29.0,
  "components": {"coverage": 0.09, "lexical": 0.49, "impact": 0.0, "verbs": 0.25, "structure": 1.0, "seniority": 1.0},
  "requirements": [
    {"requirement": "Python", "importance": 1.0, "evidence": 1.0, "matched_skill": "Python",
     "where": "experience bullet", "line": "Worked on backend APIs using Python and Flask"}
  ],
  "missing_required": ["Kafka / RabbitMQ", "Redis"],
  "weak_evidence": ["AWS", "Docker", "PostgreSQL"],
  "bullets_without_metrics": ["..."],
  "weak_bullets": ["..."],
  "years_experience": 4.5,
  "years_required": 4,
  "notes": []
}
```

## `POST /api/v1/tailor`

```json
{ "resume_text": "...", "job_description": "...", "use_llm": true, "max_pages": 1, "save": true }
```

Returns `resume` (the new text), `mode` (`rules`, `llm`, `llm+reverted`, or
`rules (llm failed)`), `before` / `after` match reports, `grounding` (fact-check of the
final text), `first_draft_grounding` (fact-check of the model's first attempt),
`repair_rounds`, `changes`, `suggestions`, `gaps`, and `run_id` if saved.

## `POST /api/v1/check`

```json
{ "original": "...", "rewritten": "..." }
```

```json
{
  "faithfulness": 85.0,
  "ok": false,
  "issues": [
    {"kind": "number", "severity": "high", "detail": "number '40%' does not appear in the original resume",
     "line": "Cut latency by 40%", "line_index": 12}
  ]
}
```

`kind` is one of `number`, `skill`, `seniority`, `scope`, `entity`, `bullet`.

## `POST /api/v1/cover-letter`

Body as `/score` plus optional `company` and `role`. Needs a key. Returns
`cover_letter` and `warnings` (numbers/skills in the letter that aren't in the resume).

## `POST /api/v1/parse`

Multipart upload (`file`): `.pdf`, `.docx`, `.txt` or `.md`, max 5 MB by default.
Returns `{"filename", "text", "chars"}`.

## `POST /api/v1/export/{fmt}`

`fmt` is `pdf`, `docx` or `md`. Body: `{"resume_text": "..."}`. Returns the file.

## History

- `GET /api/v1/history?limit=50`
- `GET /api/v1/history/{run_id}` (includes the full saved result)
- `DELETE /api/v1/history/{run_id}`

Stored in SQLite at `TALENTTUNE_DB` (default `talenttune.db`).
