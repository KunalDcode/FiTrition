"""
user_profile.py — defines the user's static profile and dynamic daily state.
Edit the profile below with YOUR actual data.
"""

from pydantic import BaseModel
from typing import Optional
from datetime import date


# ─────────────────────────────────────────────
#  STATIC PROFILE  (edit this once)
# ─────────────────────────────────────────────

class UserProfile(BaseModel):
    name: str = "Alex"
    age: int = 22
    weight_kg: float = 58.0
    height_cm: float = 172.0
    goal: str = "gain_weight"          # gain_weight | lose_weight | maintain

    # Health issues (agent will auto-adjust workouts around these)
    health_issues: list[str] = [
        "lower back pain",
        "body weakness",
        "low stamina",
    ]

    # Dietary preferences / restrictions
    diet_type: str = "non-vegetarian"  # vegetarian | vegan | non-vegetarian
    allergies: list[str] = []
    daily_calorie_target: int = 2800   # for weight gain
    protein_target_g: int = 130        # ~2.3g per kg body weight for gaining

    # Workout preferences
    workout_days_per_week: int = 5
    preferred_workout_time: str = "morning"
    available_equipment: list[str] = [
        "5kg dumbbells",
        "10kg dumbbells",
        "resistance bands",
        "pull-up bar",
        "yoga mat",
    ]

    # Weekly volume targets (agent tracks these)
    weekly_workout_targets: dict = {
        "total_sessions": 5,
        "strength_sessions": 3,
        "mobility_sessions": 2,         # important for back pain
        "cardio_sessions": 1,
    }


# ─────────────────────────────────────────────
#  DYNAMIC DAILY STATE  (agent reads/writes this)
# ─────────────────────────────────────────────

class DailyLog(BaseModel):
    log_date: str                       # "YYYY-MM-DD"
    workout_completed: bool = False
    workout_skipped: bool = False
    skip_reason: Optional[str] = None
    exercises_done: list[str] = []
    exercises_skipped: list[str] = []
    calories_consumed: Optional[int] = None
    protein_consumed_g: Optional[int] = None
    pain_level: int = 0                 # 0-10
    energy_level: int = 5              # 0-10
    notes: str = ""


class WeeklyState(BaseModel):
    week_start: str                     # "YYYY-MM-DD" (Monday)
    daily_logs: list[DailyLog] = []
    sessions_completed: int = 0
    sessions_remaining: int = 5
    deficit_exercises: list[str] = []   # carried over from skipped days
    total_calories_this_week: int = 0
    total_protein_this_week: int = 0