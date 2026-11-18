"""Badge catalogue. Each badge: key, icon, title, description, and a test on the user's statistics."""
from collections import namedtuple

Badge = namedtuple("Badge", "key icon title description check")

BADGES = [
    Badge("first_day", "🌱", "First Step", "Complete your first full day (all goals + both assessments).", lambda s: s["completed_days"] >= 1),
    Badge("streak_3", "🔥", "3-Day Streak", "Reach a streak of 3 days.", lambda s: s["longest"] >= 3),
    Badge("streak_7", "🔥", "Week Warrior", "Reach a streak of 7 days.", lambda s: s["longest"] >= 7),
    Badge("streak_14", "🔥", "Fortnight Focus", "Reach a streak of 14 days.", lambda s: s["longest"] >= 14),
    Badge("streak_21", "🔥", "Habit Builder", "Reach a streak of 21 days.", lambda s: s["longest"] >= 21),
    Badge("streak_30", "🏆", "Unstoppable", "Reach a streak of 30 days.", lambda s: s["longest"] >= 30),
    Badge("streak_40", "👑", "Challenge Champion", "Reach a streak of 40 days.", lambda s: s["longest"] >= 40),
    Badge("days_10", "📅", "Ten Good Days", "Complete 10 days in total.", lambda s: s["completed_days"] >= 10),
    Badge("days_25", "📆", "Quarter Century", "Complete 25 days in total.", lambda s: s["completed_days"] >= 25),
    Badge("comeback", "💪", "Fresh Start", "Complete a day right after missing one.", lambda s: s["comeback"]),
    Badge("goals_10", "✅", "Goal Getter", "Complete 10 daily goals.", lambda s: s["goals_done"] >= 10),
    Badge("goals_50", "🎯", "Goal Crusher", "Complete 50 daily goals.", lambda s: s["goals_done"] >= 50),
    Badge("goals_100", "🚀", "Century of Goals", "Complete 100 daily goals.", lambda s: s["goals_done"] >= 100),
    Badge("first_topic", "📘", "Topic Done", "Mark your first topic as completed.", lambda s: s["topics_completed"] >= 1),
    Badge("topics_10", "📚", "Ten Topics", "Complete 10 topics.", lambda s: s["topics_completed"] >= 10),
    Badge("first_written", "✍️", "Pen to Paper", "Submit your first written assessment.", lambda s: s["written_count"] >= 1),
    Badge("first_speaking", "🎤", "Found Your Voice", "Submit your first speaking assessment.", lambda s: s["speaking_count"] >= 1),
    Badge("written_90", "🧠", "Sharp Writer", "Score 90% or more in a written assessment.", lambda s: (s["written_best"] or 0) >= 90),
    Badge("speaking_80", "🗣️", "Clear Speaker", "Score 80% or more in a speaking assessment.", lambda s: (s["speaking_best"] or 0) >= 80),
    Badge("first_aptitude", "🧮", "Aptitude Starter", "Submit your first aptitude test.", lambda s: s["aptitude_count"] >= 1),
    Badge("aptitude_80", "⭐", "Aptitude Ace", "Score 80% or more in an aptitude test.", lambda s: (s["aptitude_best"] or 0) >= 80),
    Badge("resume_started", "🧾", "Resume Started", "Create your first resume.", lambda s: s["resume_count"] >= 1),
    Badge("ats_checked", "🔎", "Checklist Checked", "Run your first resume review.", lambda s: s["review_count"] >= 1),
    Badge("first_solve", "💻", "First Solve", "Solve your first coding problem.", lambda s: s["coding_solved"] >= 1),
    Badge("solves_5", "🧩", "Problem Solver", "Solve 5 coding problems.", lambda s: s["coding_solved"] >= 5),
    Badge("hard_solved", "🦾", "Hard Mode", "Solve a Hard coding problem.", lambda s: s["coding_hard_solved"] >= 1),
]
BADGE_BY_KEY = {b.key: b for b in BADGES}
