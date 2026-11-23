import asyncio
import json

from talenttune.llm import ScriptedLLM, extract_json
from talenttune.pipeline import tailor


def run(coro):
    return asyncio.run(coro)


def test_rules_mode_never_fabricates(resume_text, jd_text):
    res = run(tailor(resume_text, jd_text))
    assert res.mode == "rules"
    assert res.grounding.ok
    assert res.after.score >= res.before.score
    assert any("Developed backend APIs" in line for line in res.resume.split("\n"))


def test_guard_repairs_then_reverts(resume_text, jd_text):
    fab = resume_text.replace("Worked on backend APIs using Python and Flask",
                              "Engineered Kafka microservices serving 5M+ users")
    llm = ScriptedLLM([json.dumps({"resume": fab}), json.dumps({"resume": fab})])
    res = run(tailor(resume_text, jd_text, llm))
    assert res.repair_rounds == 1
    assert not res.first_draft_grounding.ok
    assert res.mode == "llm+reverted"
    assert res.grounding.ok
    assert "5M" not in res.resume
    assert "feedback" not in llm.prompts[1] and "5m" in llm.prompts[1].lower()


def test_good_draft_is_kept(resume_text, jd_text):
    good = resume_text.replace("Participated in code reviews", "Reviewed code with the team")
    llm = ScriptedLLM([json.dumps({"resume": good, "changes": ["reworded"]})])
    res = run(tailor(resume_text, jd_text, llm))
    assert res.mode == "llm" and res.repair_rounds == 0
    assert "Reviewed code with the team" in res.resume


def test_unguarded_keeps_fabrication(resume_text, jd_text):
    fab = resume_text.replace("Participated in code reviews", "Led code reviews for 12 engineers")
    res = run(tailor(resume_text, jd_text, ScriptedLLM([json.dumps({"resume": fab})]), guard=False))
    assert not res.grounding.ok


def test_bad_json_falls_back_to_rules(resume_text, jd_text):
    res = run(tailor(resume_text, jd_text, ScriptedLLM(["sorry, I can't do that"])))
    assert res.mode.startswith("rules")


def test_extract_json_variants():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Here you go:\n{"resume": "x ``` y"}') == {"resume": "x ``` y"}
