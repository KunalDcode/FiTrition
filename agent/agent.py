"""
agent.py — the fitness agent brain.

Handles:
  - Daily plan generation
  - Plan adjustment when you skip a workout or meal
  - Weekly goal tracking
  - Back pain / weakness guidance via RAG
  - Daily check-in conversation

Usage:
    python agent/agent.py plan          # generate today's workout + diet plan
    python agent/agent.py checkin       # daily check-in (log what you did)
    python agent/agent.py adjust        # tell the agent what you skipped
    python agent/agent.py status        # see this week's progress
    python agent/agent.py ask "what exercises help my back?"
"""

import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.llm_provider import get_llm, get_model_info
from utils.user_profile import UserProfile, DailyLog, WeeklyState
from knowledge_base_loader import retrieve

load_dotenv()
app = typer.Typer(help="Your personal fitness agent")
console = Console()

PLANS_PATH      = Path(os.getenv("PLANS_PATH", "./plans"))
LOGS_PATH       = Path(os.getenv("LOGS_PATH", "./logs"))
USER_STATE_FILE = Path(os.getenv("USER_STATE_FILE", "./logs/user_state.json"))

PLANS_PATH.mkdir(exist_ok=True)
LOGS_PATH.mkdir(exist_ok=True)

# ── Helpers ────────────────────────────────────────────────────────────────

def load_profile() -> UserProfile:
    return UserProfile()  # Edit defaults in utils/user_profile.py


def load_weekly_state() -> WeeklyState:
    today = date.today()
    week_start = (today - timedelta(days=today.weekday())).isoformat()

    if USER_STATE_FILE.exists():
        data = json.loads(USER_STATE_FILE.read_text())
        state = WeeklyState(**data)
        # Reset if it's a new week
        if state.week_start != week_start:
            console.print("[yellow]New week detected — resetting weekly state.[/yellow]")
            state = WeeklyState(
                week_start=week_start,
                sessions_remaining=load_profile().workout_days_per_week,
            )
    else:
        state = WeeklyState(
            week_start=week_start,
            sessions_remaining=load_profile().workout_days_per_week,
        )

    return state


def save_weekly_state(state: WeeklyState):
    LOGS_PATH.mkdir(exist_ok=True)
    USER_STATE_FILE.write_text(json.dumps(state.model_dump(), indent=2))


def build_context(profile: UserProfile, state: WeeklyState, extra_query: str = "") -> str:
    """Build the system context string for the agent."""
    today = date.today().isoformat()
    days_left = 7 - date.today().weekday()

    # RAG: pull relevant knowledge
    health_issues_query = " ".join(profile.health_issues) + " " + extra_query
    knowledge_chunks = retrieve(health_issues_query, n_results=5)
    knowledge_text = "\n\n".join(
        f"[Source: {c['source']} | relevance: {c['relevance']}]\n{c['text']}"
        for c in knowledge_chunks
    )

    return f"""
You are a personal fitness coach agent for {profile.name}.

=== USER PROFILE ===
Goal: {profile.goal}
Weight: {profile.weight_kg} kg | Height: {profile.height_cm} cm
Health issues: {', '.join(profile.health_issues)}
Diet type: {profile.diet_type}
Daily calorie target: {profile.daily_calorie_target} kcal
Protein target: {profile.protein_target_g}g/day
Available equipment: {', '.join(profile.available_equipment) or 'none (bodyweight)'}
Workout days/week: {profile.workout_days_per_week}

=== THIS WEEK STATUS (week of {state.week_start}) ===
Today: {today} ({days_left} days left in week)
Sessions completed: {state.sessions_completed} / {profile.weekly_workout_targets['total_sessions']}
Sessions remaining: {state.sessions_remaining}
Carried-over exercises: {', '.join(state.deficit_exercises) if state.deficit_exercises else 'none'}
Weekly calories so far: {state.total_calories_this_week} kcal
Weekly protein so far: {state.total_protein_this_week}g

=== RELEVANT KNOWLEDGE FROM YOUR SOLUTIONS DOC ===
{knowledge_text}

=== IMPORTANT RULES ===
- ALWAYS account for health issues. Never recommend exercises that aggravate lower back pain without modification.
- If sessions are behind target, suggest how to compensate without overtraining.
- Keep plans realistic and encouraging.
- Format plans clearly in Markdown with sections.
"""


# ── Commands ───────────────────────────────────────────────────────────────

@app.command()
def plan():
    """Generate today's workout and diet plan."""
    profile = load_profile()
    state   = load_weekly_state()
    llm     = get_llm()

    console.print(f"[dim]Model: {get_model_info()}[/dim]")

    context = build_context(profile, state, extra_query="workout plan diet plan")
    prompt  = context + "\n\nGenerate today's complete plan including:\n" \
              "1. **Workout plan** (with sets/reps, exercise modifications for back pain)\n" \
              "2. **Diet plan** (breakfast, lunch, dinner, snacks with estimated calories/protein)\n" \
              "3. **Today's focus tip** (one motivating actionable tip)\n" \
              "4. **Back pain / recovery note** if relevant\n"

    with console.status("Generating your plan..."):
        response = llm.invoke(prompt)

    plan_text = response.content

    # Save plan
    plan_file = PLANS_PATH / f"plan_{date.today().isoformat()}.md"
    plan_file.write_text(plan_text)

    console.print(Panel(Markdown(plan_text), title=f"[bold]Your Plan for {date.today().isoformat()}[/bold]", border_style="green"))
    console.print(f"[dim]Saved → {plan_file}[/dim]")


@app.command()
def checkin():
    """Log today's activity and get feedback."""
    profile = load_profile()
    state   = load_weekly_state()
    llm     = get_llm()

    console.print("[bold]Daily Check-in[/bold]\n")

    workout_done = typer.confirm("Did you complete your workout today?")
    pain_level   = typer.prompt("Pain level today (0=none, 10=severe)", default=0, type=int)
    energy_level = typer.prompt("Energy level (0=drained, 10=great)", default=5, type=int)
    calories     = typer.prompt("Approximate calories consumed today", default=0, type=int)
    protein      = typer.prompt("Approximate protein consumed today (grams)", default=0, type=int)
    notes        = typer.prompt("Any notes? (press Enter to skip)", default="")

    log = DailyLog(
        log_date=date.today().isoformat(),
        workout_completed=workout_done,
        workout_skipped=not workout_done,
        pain_level=pain_level,
        energy_level=energy_level,
        calories_consumed=calories,
        protein_consumed_g=protein,
        notes=notes,
    )

    # Update weekly state
    state.daily_logs.append(log.model_dump())
    if workout_done:
        state.sessions_completed += 1
        state.sessions_remaining = max(0, state.sessions_remaining - 1)
    state.total_calories_this_week += calories
    state.total_protein_this_week  += protein
    save_weekly_state(state)

    # Get agent feedback
    context = build_context(profile, state)
    prompt  = context + f"""
The user just completed their daily check-in:
- Workout done: {workout_done}
- Pain level: {pain_level}/10
- Energy: {energy_level}/10
- Calories today: {calories} (target: {profile.daily_calorie_target})
- Protein today: {protein}g (target: {profile.protein_target_g}g)
- Notes: {notes}

Give a short (3-5 sentences), encouraging, specific feedback:
1. Comment on today's performance
2. Note if they're on track for the week
3. One adjustment tip for tomorrow based on today's data
"""

    with console.status("Getting agent feedback..."):
        response = llm.invoke(prompt)

    console.print(Panel(response.content, title="[bold]Agent Feedback[/bold]", border_style="cyan"))


@app.command()
def adjust(
    reason: str = typer.Argument(
        default="",
        help="Why you need to adjust. E.g. 'I can't do deadlifts, my back hurts'"
    )
):
    """Tell the agent what you skipped — it will adjust the rest of your week."""
    if not reason:
        reason = typer.prompt("What do you need to adjust? (describe what you can't do today)")

    profile = load_profile()
    state   = load_weekly_state()
    llm     = get_llm()

    context = build_context(profile, state, extra_query=reason)
    prompt  = context + f"""
The user needs to adjust today's plan because: "{reason}"

Please:
1. Acknowledge the issue with empathy
2. Provide an ALTERNATIVE plan for today that avoids the problem
3. Tell them exactly how the skipped volume will be redistributed across remaining days this week
4. Make sure total weekly targets are still achievable
5. If it's a pain issue, provide specific modifications or rest guidance from the knowledge base
"""

    with console.status("Adjusting your plan..."):
        response = llm.invoke(prompt)

    console.print(Panel(Markdown(response.content), title="[bold]Adjusted Plan[/bold]", border_style="yellow"))

    # Save adjusted plan
    adj_file = PLANS_PATH / f"adjusted_{date.today().isoformat()}.md"
    adj_file.write_text(response.content)
    console.print(f"[dim]Saved → {adj_file}[/dim]")


@app.command()
def status():
    """See your weekly progress at a glance."""
    profile = load_profile()
    state   = load_weekly_state()

    cal_target  = profile.daily_calorie_target * 7
    prot_target = profile.protein_target_g * 7
    sessions    = profile.weekly_workout_targets["total_sessions"]

    console.print(Panel(
        f"""[bold]Week of {state.week_start}[/bold]

Workouts:  {state.sessions_completed}/{sessions} sessions done  {"✓" if state.sessions_completed >= sessions else f"({state.sessions_remaining} remaining)"}
Calories:  {state.total_calories_this_week} / ~{cal_target} kcal target
Protein:   {state.total_protein_this_week}g / {prot_target}g target
Carry-over: {', '.join(state.deficit_exercises) if state.deficit_exercises else 'none'}
""",
        title="Weekly Status",
        border_style="blue",
    ))


@app.command()
def ask(query: str = typer.Argument(..., help="Ask the agent anything")):
    """Ask the agent a free-form fitness question."""
    profile = load_profile()
    state   = load_weekly_state()
    llm     = get_llm()

    context = build_context(profile, state, extra_query=query)
    prompt  = context + f"\n\nUser question: {query}\n\nAnswer clearly and specifically, referencing the knowledge base where relevant."

    with console.status("Thinking..."):
        response = llm.invoke(prompt)

    console.print(Panel(Markdown(response.content), title=f"[bold]{query}[/bold]", border_style="magenta"))


if __name__ == "__main__":
    app()
