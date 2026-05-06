#!/usr/bin/env python3
"""
TalentTune-AI — CLI Quick-Start Script
Run this from your terminal for instant resume optimization.

Usage:
  python quickstart.py --resume my_resume.txt --jd job_post.txt
  python quickstart.py --resume my_resume.txt --jd job_post.txt --github https://github.com/you
  python quickstart.py --help
"""

import argparse
import sys
import os
import json
import anthropic
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="🎯 TalentTune-AI — AI Resume Optimizer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python quickstart.py --resume resume.txt --jd job.txt
  python quickstart.py --resume resume.txt --jd job.txt --cover-letter --output result.txt
  python quickstart.py --resume resume.txt --jd job.txt --github https://github.com/you
        """
    )
    parser.add_argument("--resume", required=True, help="Path to your resume (txt or md)")
    parser.add_argument("--jd",     required=True, help="Path to the job description (txt)")
    parser.add_argument("--github", default="",  help="Your GitHub profile URL (optional)")
    parser.add_argument("--linkedin", default="", help="Your LinkedIn URL (optional)")
    parser.add_argument("--output", default="optimized_resume.txt", help="Output file path")
    parser.add_argument("--cover-letter", action="store_true", help="Also generate a cover letter")
    parser.add_argument("--max-pages", type=int, default=1, choices=[1,2], help="Max resume pages")
    parser.add_argument("--api-key", default=os.environ.get("ANTHROPIC_API_KEY"), help="Anthropic API key")

    args = parser.parse_args()

    if not args.api_key:
        print("❌ Error: Set ANTHROPIC_API_KEY environment variable or pass --api-key")
        sys.exit(1)

    # Read inputs
    resume_path = Path(args.resume)
    jd_path = Path(args.jd)

    if not resume_path.exists():
        print(f"❌ Resume file not found: {args.resume}")
        sys.exit(1)
    if not jd_path.exists():
        print(f"❌ JD file not found: {args.jd}")
        sys.exit(1)

    resume_text = resume_path.read_text(encoding="utf-8")
    jd_text = jd_path.read_text(encoding="utf-8")

    client = anthropic.Anthropic(api_key=args.api_key)
    MODEL = "claude-sonnet-4-6"

    print("\n🎯 TalentTune-AI — Starting optimization pipeline...\n")

    # ── Stage 1: Analyze JD ───────────────────────────────
    print("🔍 [1/4] Analyzing job description...")
    jd_msg = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        system="You are an expert recruiter. Return ONLY valid JSON when asked.",
        messages=[{
            "role": "user",
            "content": f"""Analyze this job description. Return ONLY valid JSON:
{{
  "required_skills": [],
  "key_technologies": [],
  "ats_critical_keywords": [],
  "role_level": "mid",
  "top_keywords": []
}}

Job Description:
{jd_text}"""
        }]
    )
    jd_text_raw = jd_msg.content[0].text.strip()
    if jd_text_raw.startswith("```"):
        jd_text_raw = jd_text_raw.split("```")[1]
        if jd_text_raw.startswith("json"):
            jd_text_raw = jd_text_raw[4:]
    try:
        jd_data = json.loads(jd_text_raw)
        keywords = jd_data.get("ats_critical_keywords", [])
        print(f"   ✅ Found {len(keywords)} critical ATS keywords")
        print(f"   📌 Top keywords: {', '.join(keywords[:8])}")
    except Exception:
        jd_data = {}
        print("   ⚠️  JD analysis returned non-JSON, continuing...")

    # ── Stage 2: Before Score ─────────────────────────────
    print("\n📊 [2/4] Computing baseline ATS score...")
    before_score = _quick_ats_score(resume_text, jd_data)
    print(f"   📈 Baseline ATS Score: {before_score}/100")

    # ── Stage 3: Optimize ─────────────────────────────────
    print("\n✍️  [3/4] AI surgical rewrite in progress...")
    kw_str = ', '.join(jd_data.get('ats_critical_keywords', [])[:15])
    github_ctx = f"\nGitHub: {args.github}" if args.github else ""
    linkedin_ctx = f"\nLinkedIn: {args.linkedin}" if args.linkedin else ""

    optimize_msg = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system="""You are TalentTune-AI — an expert technical recruiter and resume optimization specialist.
RULES:
- NEVER fabricate companies, titles, dates, or achievements
- Only enhance and reframe existing experience
- Use strong action verbs: architected, engineered, built, led, scaled, reduced, shipped
- Every bullet: Action Verb + What + How + Impact""",
        messages=[{
            "role": "user",
            "content": f"""Tailor this resume for the job description.

CURRENT RESUME:{github_ctx}{linkedin_ctx}
{resume_text}

JOB DESCRIPTION:
{jd_text}

CRITICAL KEYWORDS TO INCLUDE: {kw_str}

INSTRUCTIONS:
- Rewrite to maximize alignment with JD
- NEVER fabricate experience — enhance only what exists
- Use strong action verbs with measurable impact
- Add missing ATS keywords naturally
- Reorder sections by relevance
- Max {args.max_pages} page(s)

Return ONLY valid JSON:
{{
  "resume": "FULL OPTIMIZED RESUME TEXT",
  "keywords_added": ["keyword1", "keyword2"],
  "keywords_missing": ["missing1"],
  "improvements": ["specific change 1", "specific change 2"]
}}"""
        }]
    )

    raw = optimize_msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        result = json.loads(raw)
        optimized_resume = result.get("resume", raw)
        keywords_added = result.get("keywords_added", [])
        improvements = result.get("improvements", [])
    except Exception:
        optimized_resume = raw
        keywords_added = []
        improvements = ["Resume optimized with AI assistance"]

    # ── Stage 4: After Score ──────────────────────────────
    print("\n🎯 [4/4] Recalculating ATS score...")
    after_score = _quick_ats_score(optimized_resume, jd_data)

    # ── Save Output ───────────────────────────────────────
    output_path = Path(args.output)
    output_path.write_text(optimized_resume, encoding="utf-8")

    # ── Cover Letter ──────────────────────────────────────
    cover_path = None
    if args.cover_letter:
        print("\n✉️  Generating cover letter...")
        cover_msg = client.messages.create(
            model=MODEL,
            max_tokens=1000,
            system="You are an expert career coach. Write compelling, authentic cover letters.",
            messages=[{
                "role": "user",
                "content": f"""Write a professional cover letter.

Resume (excerpt): {optimized_resume[:1200]}
Job Description: {jd_text[:1200]}

Requirements:
- 3-4 paragraphs, under 380 words
- Start with a STRONG, specific hook (not "I am writing to...")
- Body: Match top qualifications to top 3 JD requirements  
- Close with confident call to action

Return ONLY the cover letter text."""
            }]
        )
        cover_letter = cover_msg.content[0].text
        stem = output_path.stem
        cover_path = output_path.parent / f"{stem}_cover_letter.txt"
        cover_path.write_text(cover_letter, encoding="utf-8")

    # ── Print Summary ─────────────────────────────────────
    delta = after_score - before_score
    print(f"""
╔══════════════════════════════════════════════════╗
║           🎯 TALENTTUNE-AI RESULTS               ║
╠══════════════════════════════════════════════════╣
║  ATS Score:     {before_score:3d} → {after_score:3d}  (+{delta} pts)           ║
║  Keywords Added: {len(keywords_added):<3d}                              ║
║  Improvements:  {len(improvements):<3d} changes made                    ║
╠══════════════════════════════════════════════════╣
║  📄 Resume saved:  {str(output_path):<30s} ║""")
    if cover_path:
        print(f"║  ✉️  Cover letter: {str(cover_path):<30s} ║")
    print("╚══════════════════════════════════════════════════╝")

    if keywords_added:
        print(f"\n✅ Keywords added: {', '.join(keywords_added[:10])}")

    if improvements:
        print("\n✨ Key improvements:")
        for imp in improvements[:5]:
            print(f"   → {imp}")

    print(f"\n{'🚀 Great score! You\'re well-positioned.' if after_score >= 80 else '💡 Tip: Add more JD keywords to your existing experience descriptions for a higher score.'}")
    print()


def _quick_ats_score(resume: str, jd_data: dict) -> int:
    """Fast local ATS score computation."""
    r = resume.lower()
    keywords = list(set(
        jd_data.get("ats_critical_keywords", []) +
        jd_data.get("top_keywords", [])
    ))
    matched = [k for k in keywords if k.lower() in r] if keywords else []
    kw_score = min(100, round(len(matched) / max(len(keywords), 1) * 100))

    verbs = ["architected","engineered","developed","built","designed","led",
             "spearheaded","implemented","optimized","reduced","increased",
             "shipped","launched","scaled","managed","improved","automated",
             "deployed","created","established","transformed","migrated"]
    verb_count = sum(1 for v in verbs if v in r)
    verb_score = min(100, verb_count * 9)

    import re
    nums = re.findall(r'\d+[%+]?|\$\d+[KMB]?', resume)
    quant_score = min(100, len(nums) * 8)

    total = round(kw_score * 0.35 + verb_score * 0.25 + quant_score * 0.25 + 80 * 0.15)
    return total


if __name__ == "__main__":
    main()
