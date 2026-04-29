# FitForge AI

FitForge AI is a locally-run, AI-powered personal fitness agent that generates personalized daily workout and diet plans. It adapts dynamically to user feedback and utilizes **Retrieval-Augmented Generation (RAG)** to provide advice grounded in the user's own health notes, rather than generic internet data.

## 🚀 Key Features
- **Local-First Architecture:** Runs entirely from the CLI with no paid cloud dependencies.
- **Dynamic RAG Pipeline:** Uses ChromaDB and Groq (LLaMA 3.1) to ground AI responses in personal user data.
- **CLI-Native Interface:** Built with `Typer` and `Rich` for a professional, interactive terminal experience.
- **Smart Adjustments:** Retrains plan focus based on real-time feedback (e.g., pain, energy levels).

## 🛠 Tech Stack
- **Language:** Python 3.13
- **Agent Orchestration:** LangChain 0.2+
- **LLM:** Groq API (LLaMA 3.1 8B)
- **Database:** ChromaDB (Vector Store)
- **CLI:** Typer & Rich

## 📦 Project Structure
```text
fitness-agent/
├── agent/            # Core logic and CLI commands
├── data/             # Raw inputs (txt) and cleaned data (JSON)
├── knowledge_base/   # ChromaDB vector store
├── logs/             # Weekly user state and historical data
└── utils/            # Schemas and LLM providers
```

## ⚙️ Setup Instructions
**Clone the repository.**

**Install dependencies:**

**Bash**
pip install -r requirements.txt
Configure API:
Create a .env file in the root directory:

**Plaintext**
GROQ_API_KEY=your_actual_api_key_here
Initialize Data Pipeline:

**Bash**
python data_cleaner.py --input data/raw/diet_notes.txt --type diet
python data_cleaner.py --input data/raw/workout_history.txt --type workout
python knowledge_base_loader.py

## 💻 Usage
Plan: python agent/agent.py plan

Check-in: python agent/agent.py checkin

Adjust: python agent/agent.py adjust "reason"

Ask: python agent/agent.py ask "your question"

Status: python agent/agent.py status


---

### 3. Why this works for your Project
* **Engineering Maturity:** By documenting the "Project Structure" and "Tech Stack," you are signaling that you write code for *teams*, not just for yourself.
* **Ease of Testing:** When your professor or an interviewer opens your code, they don't have to hunt for how to run it. They will see the **Usage** section and immediately know how to test your work.
* **The "Why":** Including the RAG architecture explanation in the intro establishes immediately that this isn't just a basic chatbot; it is a specialized system.

Does this template capture everything, or do you want to add a section about the