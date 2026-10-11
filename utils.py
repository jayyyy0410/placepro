"""
utils.py — AI-powered calculation utilities for PlacePro
All functions are pure (no DB calls) for easy unit testing.
"""

import re
from datetime import datetime, timedelta


# ─── Job Match Score (0–100) ──────────────────────────────────────────────────

def compute_match_score(student, drive):
    """
    Returns (total: int, breakdown: dict).
    breakdown keys: 'skills' (60 pts), 'cgpa' (30 pts), 'profile' (10 pts)
    """
    # Skills overlap — 60 pts
    s_set = set(s.strip().lower() for s in (student.skills or '').split(',') if s.strip())
    d_set = set(s.strip().lower() for s in (drive.required_skills or '').split(',') if s.strip())
    if d_set:
        skills_score = round(len(s_set & d_set) / len(d_set) * 60)
    else:
        skills_score = 60   # no skill requirement = full marks

    # CGPA check — 30 pts
    cgpa_m = re.search(r'(\d+\.?\d*)', drive.eligibility_criteria or '')
    if cgpa_m and student.cgpa:
        req = float(cgpa_m.group(1))
        cgpa_score = 30 if student.cgpa >= req else max(0, round(student.cgpa / req * 30))
    elif student.cgpa:
        cgpa_score = 30     # no stated requirement = full marks
    else:
        cgpa_score = 15     # unknown CGPA

    # Profile completeness — 10 pts
    profile_score = round(compute_profile_completeness(student) / 100 * 10)

    total = min(100, skills_score + cgpa_score + profile_score)
    return total, {'skills': skills_score, 'cgpa': cgpa_score, 'profile': profile_score}


def score_label(score):
    """Human-readable label for a match score."""
    if score >= 80: return 'Excellent Match'
    if score >= 60: return 'Good Match'
    if score >= 40: return 'Fair Match'
    return 'Low Match'


def score_color(score):
    """CSS color variable name for a match score."""
    if score >= 80: return '#4ade80'
    if score >= 60: return '#a78bfa'
    if score >= 40: return '#fbbf24'
    return '#f87171'


# ─── Skills Gap ──────────────────────────────────────────────────────────────

def compute_skills_gap(student, drive):
    """
    Returns (matching: list, missing: list) with original casing from drive.
    """
    s_set = set(s.strip().lower() for s in (student.skills or '').split(',') if s.strip())
    if not drive.required_skills:
        return [], []
    d_skills = [s.strip() for s in drive.required_skills.split(',') if s.strip()]
    matching = [s for s in d_skills if s.lower() in s_set]
    missing  = [s for s in d_skills if s.lower() not in s_set]
    return matching, missing


# ─── Resume / Profile Quality Score (0–100) ──────────────────────────────────

def compute_resume_quality(student):
    """
    Returns (score: int, tips: list[str]).
    """
    score = 0
    tips  = []

    checks = [
        (student.full_name,       15, 'Add your full name'),
        (student.phone,            8, 'Add a contact phone number'),
        (student.department,       8, 'Specify your department'),
        (student.cgpa,            10, 'Enter your CGPA/GPA'),
        (student.resume_filename, 15, 'Upload your PDF resume'),
        (getattr(student, 'linkedin', None),     8, 'Add your LinkedIn profile URL'),
        (getattr(student, 'github', None),       7, 'Add your GitHub profile URL'),
        (getattr(student, 'about', None),        7, 'Write a short bio/about section'),
        (getattr(student, 'graduation_year', None), 5, 'Enter your graduation year'),
        (getattr(student, 'portfolio_url', None),   5, 'Add a portfolio/project URL'),
    ]

    for value, pts, tip in checks:
        if value:
            score += pts
        else:
            tips.append(tip)

    # Bonus for skill count (max 12 pts)
    skill_count = len([s for s in (student.skills or '').split(',') if s.strip()])
    if skill_count >= 10:
        score += 12
    elif skill_count >= 6:
        score += 8
        tips.append('Add more skills — aim for 10+ to stand out')
    elif skill_count >= 3:
        score += 4
        tips.append('Add more skills — aim for 10+ to stand out')
    else:
        tips.append('Add at least 5–10 relevant technical skills')

    return min(100, score), tips


def quality_label(score):
    if score >= 85: return ('Excellent', '#4ade80')
    if score >= 65: return ('Good',      '#a78bfa')
    if score >= 45: return ('Fair',      '#fbbf24')
    return ('Needs Work', '#f87171')


# ─── Profile Completeness (0–100) ────────────────────────────────────────────

def compute_profile_completeness(student):
    fields = [
        student.full_name,
        student.phone,
        student.department,
        student.cgpa,
        student.skills,
        student.resume_filename,
        getattr(student, 'graduation_year', None),
        getattr(student, 'about', None),
        getattr(student, 'linkedin', None),
        getattr(student, 'github', None),
    ]
    filled = sum(1 for f in fields if f)
    return round(filled / len(fields) * 100)


# ─── Recommendations ─────────────────────────────────────────────────────────

def get_recommendations(student, all_drives, applied_ids, top_n=3):
    """
    Returns list of (drive, score) tuples — top_n best matches, unapplied only.
    """
    scored = [
        (drive, compute_match_score(student, drive)[0])
        for drive in all_drives
        if drive.id not in applied_ids
    ]
    scored.sort(key=lambda x: -x[1])
    return scored[:top_n]


# ─── Progress Analytics ───────────────────────────────────────────────────────

def compute_student_progress(applications):
    """Returns a dict with counts per status and conversion rates."""
    total = len(applications)
    by_status = {}
    for app in applications:
        by_status[app.status] = by_status.get(app.status, 0) + 1

    shortlisted = by_status.get('Shortlisted', 0) + by_status.get('Interview', 0)
    selected    = by_status.get('Selected', 0) + by_status.get('Placed', 0)
    rejected    = by_status.get('Rejected', 0)

    return {
        'total':          total,
        'by_status':      by_status,
        'shortlisted':    shortlisted,
        'selected':       selected,
        'rejected':       rejected,
        'shortlist_rate': round(shortlisted / total * 100) if total else 0,
        'selection_rate': round(selected / total * 100)    if total else 0,
        'rejection_rate': round(rejected / total * 100)    if total else 0,
    }


# ─── Deadline Helpers ─────────────────────────────────────────────────────────

def drives_approaching_deadline(drives, days=5):
    """Drives with deadline within `days` days from now."""
    now    = datetime.utcnow()
    cutoff = now + timedelta(days=days)
    soon   = [d for d in drives if d.deadline and now <= d.deadline <= cutoff]
    soon.sort(key=lambda d: d.deadline)
    return soon


def days_until(deadline):
    """Whole days until deadline. None if no deadline."""
    if not deadline:
        return None
    return (deadline - datetime.utcnow()).days
