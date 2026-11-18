"""Badge catalogue. Each badge has a rule over a small dict of statistics (see services.gather_stats)."""

CATALOG = {
    "first_day": {"title": "First day done", "icon": "🌱", "description": "Finished all goals and both assessments in one day.", "rule": lambda s: s["active_days"] >= 1},
    "streak_3": {"title": "3-day streak", "icon": "🔥", "description": "A streak of 3 successful days.", "rule": lambda s: s["longest"] >= 3},
    "streak_7": {"title": "One full week", "icon": "🏅", "description": "A streak of 7 successful days.", "rule": lambda s: s["longest"] >= 7},
    "streak_14": {"title": "Two weeks strong", "icon": "💪", "description": "A streak of 14 successful days.", "rule": lambda s: s["longest"] >= 14},
    "streak_21": {"title": "Habit builder", "icon": "🧱", "description": "A streak of 21 successful days.", "rule": lambda s: s["longest"] >= 21},
    "streak_30": {"title": "30-day streak", "icon": "🏆", "description": "A streak of 30 successful days.", "rule": lambda s: s["longest"] >= 30},
    "streak_40": {"title": "Challenge complete", "icon": "👑", "description": "A streak of all 40 days.", "rule": lambda s: s["longest"] >= 40},
    "days_10": {"title": "10 active days", "icon": "📅", "description": "10 successful learning days in total.", "rule": lambda s: s["active_days"] >= 10},
    "days_25": {"title": "25 active days", "icon": "🗓️", "description": "25 successful learning days in total.", "rule": lambda s: s["active_days"] >= 25},
    "goals_10": {"title": "10 goals done", "icon": "✅", "description": "Completed 10 daily goals.", "rule": lambda s: s["goals_done"] >= 10},
    "goals_50": {"title": "50 goals done", "icon": "🎯", "description": "Completed 50 daily goals.", "rule": lambda s: s["goals_done"] >= 50},
    "first_written": {"title": "Written test taken", "icon": "✍️", "description": "Submitted your first written assessment.", "rule": lambda s: s["written"] >= 1},
    "first_speaking": {"title": "Found your voice", "icon": "🎤", "description": "Submitted your first speaking assessment.", "rule": lambda s: s["speaking"] >= 1},
    "first_aptitude": {"title": "Aptitude started", "icon": "🧮", "description": "Finished your first aptitude test.", "rule": lambda s: s["aptitude_tests"] >= 1},
    "aptitude_80": {"title": "Aptitude ace", "icon": "🌟", "description": "Scored 80% or more on an aptitude test.", "rule": lambda s: s["aptitude_best"] >= 80},
    "first_dsa": {"title": "First problem solved", "icon": "💻", "description": "Solved your first DSA problem.", "rule": lambda s: s["dsa_solved"] >= 1},
    "dsa_5": {"title": "5 problems solved", "icon": "🧩", "description": "Solved 5 DSA problems.", "rule": lambda s: s["dsa_solved"] >= 5},
}
