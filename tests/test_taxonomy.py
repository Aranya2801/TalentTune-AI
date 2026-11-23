from talenttune.taxonomy import load_taxonomy

tax = load_taxonomy()


def found(text):
    return [m.skill for m in tax.find(text)]


def test_symbols_and_dots():
    assert found("C++, C#, Node.js and .NET") == ["C++", "C#", "Node.js", ".NET"]
    assert found("CI/CD with GitHub Actions") == ["CI/CD", "GitHub Actions"]


def test_longest_alias_wins():
    assert found("React Native app") == ["React Native"]
    assert found("Spring Boot services") == ["Spring Boot"]


def test_case_sensitive_aliases():
    # "react" the verb and "rest" the noun shouldn't count
    assert found("we react quickly and rest on weekends") == []
    assert found("Built with React and REST") == ["React", "REST APIs"]


def test_no_partial_words():
    assert found("javascripts") == []
    assert "Java" not in found("JavaScript")


def test_implies_is_transitive():
    assert {"Kubernetes", "Docker"} <= tax.closure({"Helm"})
    assert "Python" in tax.closure({"FastAPI"})
    assert "FastAPI" not in tax.closure({"Python"})
