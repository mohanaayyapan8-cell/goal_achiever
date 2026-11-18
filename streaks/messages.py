"""Motivational texts shown on the dashboard and in notifications."""

MILESTONES = {
    3: "Three days in a row: the habit is forming!",
    7: "A full week! That is real consistency.",
    14: "Two weeks strong. You are building something lasting.",
    21: "21 days: this is becoming a habit.",
    30: "30 days! Look how far you have come.",
    40: "All 40 days! You finished the challenge. Be proud.",
}

DAY_DONE = "Excellent work! You completed today's learning goals. Keep moving forward!"
MISSED = "You missed yesterday's target. Don't give up. Your next successful day is a fresh opportunity!"


def day_done_message(streak):
    extra = MILESTONES.get(streak)
    return f"{DAY_DONE} {extra}" if extra else DAY_DONE


def status_message(state, current, req):
    if state == "completed_today":
        return day_done_message(current)
    if state == "pending":
        return f"You are on a {current}-day streak. Finish today's goals and both assessments to extend it!"
    if state == "interrupted":
        return f"{MISSED} Your {current}-day streak is paused: complete today to keep it going. Missing another day resets it."
    if state == "reset":
        return "Your streak was reset after two missed days, but all your progress and history are safe. Today is a fresh start!"
    if state == "outside":
        return "Streaks run during your 40-day challenge. Start or check your planner."
    return "Complete today's goals and both assessments to start your first streak."
