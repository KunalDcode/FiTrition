"""
knowledge_base_loader.py — Step 2 of the pipeline.

Loads cleaned JSON files into a local ChromaDB vector store.
The agent uses this for RAG (retrieval-augmented generation) —
e.g. "what should I do for lower back pain?" retrieves relevant chunks.

Usage:
    python knowledge_base_loader.py --reset        # wipe and rebuild from scratch
    python knowledge_base_loader.py               # add/update only
"""

import json
import os
import typer
from pathlib import Path
from rich.console import Console
import chromadb
from dotenv import load_dotenv

load_dotenv()
app = typer.Typer()
console = Console()

CHROMA_PATH = os.getenv("CHROMA_DB_PATH", "./knowledge_base/chroma_db")
CLEANED_DIR = Path("data/cleaned")


def get_chroma_collection(reset: bool = False):
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    if reset:
        try:
            client.delete_collection("fitness_knowledge")
            console.print("[yellow]Existing collection wiped.[/yellow]")
        except Exception:
            pass
    collection = client.get_or_create_collection(
        name="fitness_knowledge",
        metadata={"hnsw:space": "cosine"},
    )
    return collection


def flatten_to_text(entry: dict, data_type: str) -> str:
    """Convert a structured JSON entry into a searchable text chunk."""
    if data_type == "solutions":
        parts = [
            f"Topic: {entry.get('topic', '')}",
            f"Problem: {entry.get('problem', '')}",
            f"Solution: {entry.get('solution', '')}",
            f"Exercises: {', '.join(entry.get('exercises', []))}",
            f"Diet tips: {', '.join(entry.get('diet_tips', []))}",
            f"Precautions: {', '.join(entry.get('precautions', []))}",
        ]
    elif data_type == "diet":
        parts = [
            f"Meal: {entry.get('meal', '')}",
            f"Foods: {', '.join(entry.get('foods', []))}",
            f"Calories: {entry.get('calories_approx', 'unknown')}",
            f"Protein: {entry.get('protein_g_approx', 'unknown')}g",
            f"Notes: {entry.get('notes', '')}",
        ]
    elif data_type == "workout":
        exercises = entry.get("exercises", [])
        ex_text = "; ".join(
            f"{e.get('name')} {e.get('sets')}x{e.get('reps_or_duration')}"
            for e in exercises if e.get("name")
        )
        parts = [
            f"Session type: {entry.get('session_type', '')}",
            f"Exercises: {ex_text}",
            f"Duration: {entry.get('duration_mins', '?')} mins",
            f"Feeling: {entry.get('how_it_felt', '')}",
            f"Pain noted: {entry.get('pain_noted', '')}",
        ]
    else:
        parts = [str(entry)]

    return "\n".join(p for p in parts if p.split(": ", 1)[-1].strip())


@app.command()
def load(
    reset: bool = typer.Option(False, "--reset", help="Wipe DB and rebuild from scratch"),
):
    collection = get_chroma_collection(reset=reset)

    json_files = list(CLEANED_DIR.glob("*.json"))
    if not json_files:
        console.print("[red]No cleaned JSON files found in data/cleaned/[/red]")
        console.print("Run data_cleaner.py first.")
        raise typer.Exit(1)

    total_added = 0

    for json_file in json_files:
        # Infer data type from filename
        name = json_file.stem.lower()
        if "diet" in name:
            data_type = "diet"
        elif "workout" in name:
            data_type = "workout"
        elif "solution" in name:
            data_type = "solutions"
        else:
            data_type = "general"

        entries = json.loads(json_file.read_text())
        if not isinstance(entries, list):
            entries = [entries]

        documents, metadatas, ids = [], [], []

        for i, entry in enumerate(entries):
            doc_id = f"{json_file.stem}_{i}"
            text = flatten_to_text(entry, data_type)
            tags = entry.get("tags", [])

            documents.append(text)
            metadatas.append({
                "source": json_file.name,
                "type": data_type,
                "tags": ",".join(tags) if tags else "",
                "index": i,
            })
            ids.append(doc_id)

        collection.upsert(documents=documents, metadatas=metadatas, ids=ids)
        console.print(f"[green]✓ Loaded {len(entries)} chunks from {json_file.name}[/green]")
        total_added += len(entries)

    console.print(f"\n[bold green]Knowledge base ready — {total_added} total chunks indexed.[/bold green]")
    console.print(f"[dim]Stored at: {CHROMA_PATH}[/dim]")


def retrieve(query: str, n_results: int = 4, tag_filter: str = None) -> list[dict]:
    """Retrieve relevant knowledge chunks. Called by the agent."""
    collection = get_chroma_collection()

    where = {"tags": {"$contains": tag_filter}} if tag_filter else None

    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        chunks.append({
            "text": doc,
            "source": meta.get("source"),
            "type": meta.get("type"),
            "relevance": round(1 - dist, 3),
        })

    return chunks


if __name__ == "__main__":
    app()
