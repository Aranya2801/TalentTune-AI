# TalentTune-AI — Daily Usage Guide

This guide covers the fastest ways to use TalentTune-AI every day when applying for jobs.

---

## ⚡ Fastest Workflow: CLI Script

**Setup once:**
```bash
# In your shell config (~/.bashrc or ~/.zshrc)
export ANTHROPIC_API_KEY="sk-ant-..."
alias talenttune="python /path/to/TalentTune-AI/quickstart.py"
```

**Daily use:**
```bash
# 1. Save the job description to a text file
pbpaste > job.txt          # Mac: paste from clipboard
xclip -o > job.txt         # Linux

# 2. Run optimization
talenttune --resume my_resume.txt --jd job.txt --cover-letter

# 3. Open the output
open optimized_resume.txt
```

Done. Takes about 30 seconds. 🚀

---

## 🌐 Web App Workflow

1. Open `frontend/index.html` in your browser (or visit `http://localhost:80` with Docker)
2. Enter your Anthropic API key once (it's saved in your browser)
3. Paste resume → Paste JD → Click Optimize
4. Review ATS score improvement
5. Copy optimized resume → Apply

---

## 📋 One-Time Setup: Your Master Resume

Keep a `my_resume.txt` file that's your **complete** experience history. Don't trim anything. TalentTune-AI will pull the most relevant parts for each JD.

```
my_master_resume.txt   ← Never edit this manually, keep it comprehensive
```

---

## 🎯 Tips for Maximum ATS Score

1. **Include more numbers in your master resume** — even rough ones
   - "Reduced load time" → "Reduced load time by ~40%"
   - "Served many users" → "Served 10K+ daily users"

2. **Use full technology names** — not abbreviations
   - "ML" → "Machine Learning"
   - "k8s" → "Kubernetes"

3. **Add a Skills section** if you don't have one — ATS systems scan it heavily

4. **Keep formatting plain text** — no tables, no columns, no text boxes
   - These confuse ATS parsers and will tank your score

5. **Target score 80+** — Above 80 your resume typically passes initial ATS filters

---

## 📁 Recommended File Structure

```
~/job-search/
├── my_master_resume.txt       ← Your comprehensive resume
├── TalentTune-AI/             ← This project
├── applications/
│   ├── 2025-05-DataflowInc/
│   │   ├── job_description.txt
│   │   ├── optimized_resume.txt
│   │   └── cover_letter.txt
│   └── 2025-05-TechCorp/
│       └── ...
```

---

## 🔄 Batch Applications (10 Jobs at Once)

```bash
#!/bin/bash
# batch_optimize.sh — optimize for multiple jobs

JD_FOLDER="./job_descriptions"
RESUME="my_resume.txt"

for jd in "$JD_FOLDER"/*.txt; do
    name=$(basename "$jd" .txt)
    echo "🎯 Optimizing for: $name"
    python quickstart.py \
        --resume "$RESUME" \
        --jd "$jd" \
        --output "applications/$name/resume.txt" \
        --cover-letter
    echo "✅ Done: $name"
    sleep 3   # Respect API rate limits
done
echo "🏁 All done!"
```

---

## 🧠 Understanding Your ATS Score

| Score | What It Means |
|-------|---------------|
| 90+   | Excellent — very likely to pass ATS |
| 80-89 | Good — should pass most ATS systems |
| 70-79 | Fair — may get filtered at strict companies |
| <70   | Needs work — add more keywords from JD |

---

## ❓ FAQ

**Q: Will AI fabricate experience?**
A: No. TalentTune-AI is explicitly instructed never to invent jobs, companies, dates, or achievements. It only rephrases and enhances what you provide.

**Q: Is my resume sent to any server?**
A: With the web app, your resume goes directly to Anthropic's API using your own key. With the Python script, same. Nothing is stored on any TalentTune-AI server.

**Q: How often should I update my master resume?**
A: After every project, achievement, or job change. The more comprehensive it is, the better TalentTune-AI can tailor for any role.

**Q: What's the best model to use?**
A: Claude Sonnet 4.6 (default) — it's the best balance of speed, quality, and cost for resume work.
