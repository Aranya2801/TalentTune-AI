from talenttune.grounding import check, revert_flagged


def kinds(original, rewritten):
    return {i.kind for i in check(original, rewritten).issues if i.severity != "low"}


def test_identity_is_clean(resume_text):
    rep = check(resume_text, resume_text)
    assert rep.ok and rep.faithfulness == 100


def test_catches_new_number(resume_text):
    new = resume_text.replace("Fixed bugs and improved code performance",
                              "Fixed bugs and improved code performance by 35%")
    assert "number" in kinds(resume_text, new)


def test_catches_borrowed_number(resume_text):
    # 8.2 exists (the GPA) but has nothing to do with this bullet
    new = resume_text.replace("Deployed applications to servers", "Deployed 8.2 applications to servers")
    assert "number" in kinds(resume_text, new)


def test_catches_skill_from_jd(resume_text):
    new = resume_text.replace("Worked on backend APIs using Python and Flask",
                              "Worked on backend APIs using Python, Flask and Kafka")
    assert "skill" in kinds(resume_text, new)


def test_implied_skill_is_fine(resume_text):
    # the original has Flask, so saying Python is not new information
    new = resume_text.replace("Built a tool that optimizes resumes using AI",
                              "Built a Python tool that optimizes resumes using AI")
    assert "skill" not in kinds(resume_text, new)


def test_catches_title_inflation(resume_text):
    new = resume_text.replace("Software Engineer — StartupXYZ", "Senior Software Engineer — StartupXYZ")
    assert "seniority" in kinds(resume_text, new)


def test_catches_scope_inflation(resume_text):
    new = resume_text.replace("Participated in code reviews", "Led code reviews")
    assert "scope" in kinds(resume_text, new)


def test_catches_invented_bullet(resume_text):
    new = resume_text.replace("• Participated in code reviews",
                              "• Participated in code reviews\n• Negotiated vendor contracts for the whole company")
    assert "bullet" in kinds(resume_text, new)


def test_faithful_rewording_passes(resume_text):
    new = (resume_text.replace("Worked on backend APIs", "Developed backend APIs")
           .replace("Helped maintain", "Maintained"))
    assert check(resume_text, new).ok


def test_revert_restores_original_lines(resume_text):
    bad = resume_text.replace("Worked on backend APIs using Python and Flask",
                              "Engineered microservices in FastAPI serving 5M users")
    fixed = revert_flagged(resume_text, bad, check(resume_text, bad))
    assert "Worked on backend APIs using Python and Flask" in fixed
    assert check(resume_text, fixed).ok
