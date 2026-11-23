from talenttune.jd import parse_jd


def by_label(jd):
    return {r.label: r for r in jd.requirements}


def test_sections_and_weights(jd_text):
    jd = parse_jd(jd_text)
    reqs = by_label(jd)
    assert reqs["Python"].importance == 1.0
    assert reqs["Prometheus"].section == "preferred"
    assert reqs["Prometheus"].importance < reqs["Python"].importance
    assert jd.min_years == 4


def test_benefits_are_ignored(jd_text):
    jd = parse_jd(jd_text)
    assert not any("learning budget" in ln for ln in jd.content_lines)


def test_or_group(jd_text):
    reqs = by_label(parse_jd(jd_text))
    assert "Kafka / RabbitMQ" in reqs
    assert "Kafka" not in reqs and "RabbitMQ" not in reqs


def test_bracketed_examples_count_less(jd_text):
    reqs = by_label(parse_jd(jd_text))
    assert reqs["EC2"].importance < reqs["AWS"].importance
    # Kubernetes is listed next to Docker, not as an example of it
    assert reqs["Kubernetes"].importance == 1.0


def test_inline_preferred():
    jd = parse_jd("Data Engineer\n\nRequirements:\n- Python and SQL\n- Airflow is a plus\n")
    reqs = by_label(jd)
    assert reqs["Airflow"].section == "preferred"
    assert reqs["Python"].section == "required"
