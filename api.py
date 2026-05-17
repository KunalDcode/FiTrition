"""
api.py — FitForge AI REST API
Wraps agent commands as HTTP endpoints for the frontend.
"""

import json
import sys
from pathlib import Path
from datetime import date, timedelta

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent))
from utils.llm_provider import get_llm
from utils.user_profile import UserProfile, DailyLog, WeeklyState
from knowledge_base_loader import retrieve

app = FastAPI(title="FitForge AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Helpers ────────────────────────────────────────────────────────────────

USER_STATE_FILE = Path("./logs/user_state.json")
PLANS_PATH      = Path("./plans")
PLANS_PATH.mkdir(exist_ok=True)
Path("./logs").mkdir(exist_ok=True)

def load_profile():
    return UserProfile()

def load_state():
    today      = date.today()
    week_start = (today - timedelta(days=today.weekday())).isoformat()
    if USER_STATE_FILE.exists():
        content = USER_STATE_FILE.read_text(encoding="utf-8").strip()
        if content:
            try:
                data  = json.loads(content)
                state = WeeklyState(**data)
                if state.week_start != week_start:
                    state = WeeklyState(week_start=week_start, sessions_remaining=5)
                return state
            except Exception:
                pass
    return WeeklyState(week_start=week_start, sessions_remaining=5)

def save_state(state: WeeklyState):
    USER_STATE_FILE.write_text(json.dumps(state.model_dump(), indent=2), encoding="utf-8")

def build_context(profile, state, query=""):
    today  = date.today().isoformat()
    chunks = retrieve(" ".join(profile.health_issues) + " " + query, n_results=6)
    knowledge = "\n\n".join(f"[{c['source']}]\n{c['text']}" for c in chunks)

    non_neg  = "\n".join(f"- {x}" for x in getattr(profile, 'daily_non_negotiables', []))
    desk_brk = "\n".join(f"- {x}" for x in getattr(profile, 'desk_break_routine', []))
    split    = getattr(profile, 'weekly_split', {})
    today_split = split.get(date.today().strftime("%A"), "General training")

    return f"""
You are FitForge AI — Dual-Expert: Pro Strength Coach & AI Clinical Nutritionist.

CRITICAL CONSTRAINTS — NEVER VIOLATE:
- HARDGAINER: 53kg → 90kg goal. Every decision serves mass gain.
- CHRONIC BACK PAIN: Never suggest heavy deadlifts, barbell squats, sit-ups.
- VEGETARIAN: No meat, fish, eggs, protein powder. Use paneer, dal, soya, curd, milk, chana.
- IRON DEFICIENCY: Regularly include iron-rich foods + Vitamin C combos.
- EQUIPMENT: Bricks, pull-up bar, water bottles, yoga mat ONLY.
- NO MILK + BANANA together.
- CALORIE GAP: User eats ~1600 kcal. Must reach 2800-3000 kcal.

FIXED DAILY NON-NEGOTIABLES (include in EVERY plan):
{non_neg}

FIXED FIRST MORNING MEAL: {getattr(profile, 'fixed_morning_meal', '')}

DESK BREAK ROUTINE (include in every plan):
{desk_brk}

TODAY ({today}) WORKOUT TYPE: {today_split}

WEEKLY STATE:
Sessions done: {state.sessions_completed}/5
Calories this week: {state.total_calories_this_week}
Protein this week: {state.total_protein_this_week}g

KNOWLEDGE BASE:
{knowledge}
"""

# ── Request Models ─────────────────────────────────────────────────────────

class AdjustRequest(BaseModel):
    reason: str

class CheckinRequest(BaseModel):
    workout_done: bool
    pain_level: int
    energy_level: int
    calories: int
    protein: int
    notes: str = ""

class AskRequest(BaseModel):
    question: str

# ── Endpoints ──────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "FitForge AI is running"}

@app.get("/api/plan")
def get_plan():
    profile = load_profile()
    state   = load_state()
    llm     = get_llm()
    context = build_context(profile, state, "workout diet plan")
    prompt  = context + """
Generate today's complete plan:

## 1. MORNING ROUTINE
Fixed 10-min back + kegel + stretch routine. List each exercise with reps.

## 2. WORKOUT
Today's session based on the weekly split. Exercises with sets/reps using available equipment.
Include back-pain modifications. Explain why each is chosen.

## 3. DIET PLAN
All meals. Start with the fixed morning nut shake. Use vegetarian Indian foods only.
Hit ~2800 kcal and ~130g protein across 5-6 meals.

## 4. CALORIE UPGRADE TIP
One specific addition for +200-300 kcal without extra volume.

## 5. DESK BREAK SCHEDULE
When and what to do during work hours.

## 6. BACK PAIN NOTE
Today's specific precaution.
"""
    response  = llm.invoke(prompt)
    plan_text = response.content
    plan_file = PLANS_PATH / f"plan_{date.today().isoformat()}.md"
    plan_file.write_text(plan_text, encoding="utf-8")
    return {"plan": plan_text, "date": date.today().isoformat()}

@app.post("/api/checkin")
def post_checkin(data: CheckinRequest):
    profile = load_profile()
    state   = load_state()
    llm     = get_llm()

    log = DailyLog(
        log_date=date.today().isoformat(),
        workout_completed=data.workout_done,
        workout_skipped=not data.workout_done,
        pain_level=data.pain_level,
        energy_level=data.energy_level,
        calories_consumed=data.calories,
        protein_consumed_g=data.protein,
        notes=data.notes,
    )
    state.daily_logs.append(log.model_dump())
    if data.workout_done:
        state.sessions_completed += 1
        state.sessions_remaining = max(0, state.sessions_remaining - 1)
    state.total_calories_this_week += data.calories
    state.total_protein_this_week  += data.protein
    save_state(state)

    context = build_context(profile, state)
    prompt  = context + f"""
Check-in: workout={data.workout_done}, pain={data.pain_level}/10,
energy={data.energy_level}/10, calories={data.calories}, protein={data.protein}g, notes={data.notes}

Give 4-5 sentence specific feedback:
1. Today's performance
2. Calorie/protein gap — exact food to eat tonight to close it
3. Back pain comment if pain > 3
4. One thing to do differently tomorrow
"""
    response = llm.invoke(prompt)
    return {"feedback": response.content, "state": state.model_dump()}

@app.post("/api/adjust")
def post_adjust(data: AdjustRequest):
    profile = load_profile()
    state   = load_state()
    llm     = get_llm()
    context = build_context(profile, state, data.reason)
    prompt  = context + f"""
User can't follow today's plan: "{data.reason}"

## 1. ALTERNATIVE PLAN
Modified workout avoiding the issue. Back-safe always.

## 2. WEEK REDISTRIBUTION
How missed volume spreads across {state.sessions_remaining} remaining sessions.

## 3. CALORIE CATCH-UP
How to still hit calorie target today despite the change.
"""
    response = llm.invoke(prompt)
    return {"adjusted_plan": response.content}

@app.get("/api/status")
def get_status():
    profile = load_profile()
    state   = load_state()
    return {
        "week_start":        state.week_start,
        "sessions_completed": state.sessions_completed,
        "sessions_target":    profile.weekly_workout_targets["total_sessions"],
        "sessions_remaining": state.sessions_remaining,
        "calories_this_week": state.total_calories_this_week,
        "calorie_target":     profile.daily_calorie_target * 7,
        "protein_this_week":  state.total_protein_this_week,
        "protein_target":     profile.protein_target_g * 7,
        "weight_goal":        "53kg → 90kg",
    }

@app.post("/api/ask")
def post_ask(data: AskRequest):
    profile  = load_profile()
    state    = load_state()
    llm      = get_llm()
    context  = build_context(profile, state, data.question)
    prompt   = context + f"""
Question: {data.question}
Answer specifically. Reference knowledge base. Always respect: vegetarian, hardgainer, back pain, low equipment.
"""
    response = llm.invoke(prompt)
    return {"answer": response.content}