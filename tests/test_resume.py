from datetime import date

from talenttune.resume import parse_resume, section_of_header


def test_sections(resume_text):
    r = parse_resume(resume_text)
    assert {"summary", "experience", "projects", "skills", "education"} <= r.sections
    assert len(r.bullets) == 10


def test_evidence_depends_on_where(resume_text):
    r = parse_resume(resume_text)
    assert r.evidence["Python"].weight == 1.0          # used in an experience bullet
    assert r.evidence["Docker"].weight < 0.5           # only in the skills list


def test_years_merge_overlaps():
    text = """EXPERIENCE
Engineer — A (Jan 2020 – Dec 2021)
• did things
Engineer — B (Jun 2021 – Dec 2022)
• more things
"""
    r = parse_resume(text, today=date(2026, 1, 1))
    assert r.years_experience == 3.0


def test_present_uses_today():
    r = parse_resume("EXPERIENCE\nDev — X (Jan 2025 – Present)\n• x", today=date(2026, 1, 1))
    assert r.years_experience == 1.1


def test_header_aliases():
    assert section_of_header("WORK EXPERIENCE") == "experience"
    assert section_of_header("Technical Skills:") == "skills"
    assert section_of_header("Built an API") is None


def test_list_like_bullet_gets_list_credit():
    text = "EXPERIENCE\nDev — X (2020 – 2022)\n• Python, Docker, Kubernetes, Kafka, Redis, AWS, Terraform\n"
    r = parse_resume(text)
    assert r.evidence["Kafka"].weight <= 0.35
