from talenttune.scoring import score


def test_report_is_explainable(resume_text, jd_text):
    rep = score(resume_text, jd_text)
    assert 0 <= rep.score <= 100
    assert set(rep.components) == {"coverage", "lexical", "impact", "verbs", "structure", "seniority"}
    py = next(m for m in rep.requirements if m.requirement == "Python")
    assert py.where == "experience bullet" and py.line
    assert "Redis" in rep.missing_required
    assert "Docker" in rep.weak_evidence


def test_stuffing_the_skills_list_barely_helps(resume_text, jd_text):
    base = score(resume_text, jd_text).score
    stuffed = resume_text + "\nMore: Kafka, Redis, Kubernetes, Microservices, CI/CD, Distributed Systems\n"
    assert score(stuffed, jd_text).score - base < 8


def test_real_evidence_helps_more_than_listing(resume_text, jd_text):
    listed = resume_text + "\nMore: Redis\n"
    used = resume_text.replace(
        "• Fixed bugs and improved code performance",
        "• Fixed bugs and improved code performance\n• Added Redis caching to the product API",
    )
    assert score(used, jd_text).score > score(listed, jd_text).score


def test_dates_are_not_metrics():
    from talenttune.text import metric_numbers

    assert metric_numbers("(Jan 2023 – Present)") == []
    assert metric_numbers("cut p95 from 900ms to 120ms") == ["900ms", "120ms"]
