"""
data_cleaner.py — Step 1 of the pipeline.

Run this once (or whenever you add new raw data).
It takes your messy diet notes, workout history, and solutions doc
and converts them into structured JSON using the LLM.

Usage:
    python data_cleaner.py --input data/raw/my_notes.txt --type diet
    python data_cleaner.py --input data/raw/workouts.txt --type workout
    python data_cleaner.py --input data/raw/solutions.txt --type solutions
"""

import json
import typer
from pathlib import Path
from rich.console import Console
from utils.llm_provider import get_llm, get_model_info

app = typer.Typer()
console = Console()

PROMPTS = {
    "diet": """
You are a nutrition data structuring assistant.
Convert the following raw diet notes into a structured JSON array.
Each entry should have: {{ "meal": "", "foods": [], "calories_approx": 0, "protein_g_approx": 0, "time": "", "notes": "" }}
If any field is missing, use null. Return ONLY valid JSON, no explanation.

RAW NOTES:
{raw_text}
""",

    "workout": """
You are a fitness data structuring assistant.
Convert the following raw workout notes into a structured JSON array.
Each entry should have: {{ "date": "", "session_type": "", "exercises": [{{"name": "", "sets": 0, "reps_or_duration": "", "weight_kg": 0, "notes": ""}}], "duration_mins": 0, "how_it_felt": "", "pain_noted": "" }}
If any field is missing, use null. Return ONLY valid JSON, no explanation.

RAW NOTES:
{raw_text}
""",

    "solutions": """
You are a fitness knowledge base assistant.
Convert the following solutions/advice document into a structured JSON array of knowledge chunks.
Each chunk: {{ "topic": "", "problem": "", "solution": "", "exercises": [], "diet_tips": [], "precautions": [], "tags": [] }}
Tags should include relevant keywords like: back_pain, weight_gain, weakness, stamina, diet, recovery, etc.
Return ONLY valid JSON, no explanation.

RAW DOCUMENT:
{raw_text}
""",
}


@app.command()
def clean(
    input: Path = typer.Option(..., help="Path to raw input file"),
    type: str  = typer.Option(..., help="Type: diet | workout | solutions"),
    output: Path = typer.Option(None, help="Output path (auto-generated if not set)"),
):
    if type not in PROMPTS:
        console.print(f"[red]Unknown type '{type}'. Choose: diet | workout | solutions[/red]")
        raise typer.Exit(1)

    if not input.exists():
        console.print(f"[red]File not found: {input}[/red]")
        raise typer.Exit(1)

    raw_text = input.read_text(encoding="utf-8")
    console.print(f"[cyan]Using model:[/cyan] {get_model_info()}")
    console.print(f"[cyan]Cleaning:[/cyan] {input.name} as type=[bold]{type}[/bold]")

    llm = get_llm()
    prompt = PROMPTS[type].format(raw_text=raw_text)

    with console.status("Calling LLM to structure your data..."):
        response = llm.invoke(prompt)

    raw_output = response.content.strip()

    # Strip markdown code fences if present
    if raw_output.startswith("```"):
        raw_output = "\n".join(raw_output.split("\n")[1:-1])

    try:
        structured = json.loads(raw_output)
    except json.JSONDecodeError as e:
        console.print(f"[red]JSON parse error:[/red] {e}")
        console.print("[yellow]Raw LLM output saved to data/cleaned/debug_output.txt[/yellow]")
        Path("data/cleaned/debug_output.txt").write_text(raw_output)
        raise typer.Exit(1)

    # Save output
    if output is None:
        output = Path(f"data/cleaned/{input.stem}_{type}_cleaned.json")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(structured, indent=2, ensure_ascii=False), encoding="utf-8")

    console.print(f"[green]✓ Saved {len(structured)} structured entries → {output}[/green]")


if __name__ == "__main__":
    app()