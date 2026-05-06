# Contributing to TalentTune-AI

Thank you for helping make TalentTune-AI better! 🎯

## How to Contribute

### 🐛 Bug Reports
Open an issue with:
- **Environment**: OS, Python version, Node version
- **Steps to reproduce**: Exact steps that trigger the bug
- **Expected vs actual**: What should happen vs what does happen
- **Logs**: Relevant error output

### ✨ Feature Requests
Open an issue tagged `enhancement` with:
- **Use case**: What problem does this solve?
- **Proposed solution**: How should it work?
- **Alternatives considered**: What else did you think about?

### 🔧 Pull Requests

1. **Fork** the repository
2. **Create a branch**: `git checkout -b feature/your-feature-name`
3. **Make your changes** with clear, focused commits
4. **Test your changes** thoroughly
5. **Submit a PR** with a clear description

#### Commit Convention
```
feat: add LinkedIn profile scraping
fix: handle empty resume text gracefully
docs: update API endpoint reference
refactor: simplify ATS score computation
test: add unit tests for keyword extractor
```

#### Code Standards
- Python: Follow PEP 8, use type hints, docstrings for all functions
- JavaScript: ESLint-compatible, descriptive variable names
- All new API endpoints must have docstrings
- Never commit API keys or secrets

## Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/TalentTune-AI.git
cd TalentTune-AI

# Set up backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env   # Add your API key

# Run backend
uvicorn main:app --reload

# Run frontend (separate terminal)
cd frontend
# Just open index.html in browser, or use:
python -m http.server 5173
```

## Areas Where Help is Needed
- [ ] Unit tests for `services/claude_service.py`
- [ ] PDF resume parsing improvements
- [ ] LinkedIn profile scraper integration
- [ ] Browser extension prototype
- [ ] Dark/light theme toggle
- [ ] Resume diff viewer (before vs after side-by-side)
- [ ] Multi-language support

## Code of Conduct
Be kind, respectful, and constructive. We're all here to build something useful.
