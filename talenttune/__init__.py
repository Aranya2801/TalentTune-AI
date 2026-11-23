"""TalentTune-AI: explainable resume/JD matching and fact-checked tailoring."""

__version__ = "0.3.0"

from .grounding import check  # noqa: E402
from .jd import parse_jd  # noqa: E402
from .resume import parse_resume  # noqa: E402
from .scoring import score  # noqa: E402

__all__ = ["check", "parse_jd", "parse_resume", "score", "__version__"]
