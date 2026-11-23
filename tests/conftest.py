from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def resume_text():
    return (ROOT / "examples" / "resume.txt").read_text(encoding="utf-8")


@pytest.fixture
def jd_text():
    return (ROOT / "examples" / "job_description.txt").read_text(encoding="utf-8")
