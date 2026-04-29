"""
llm_provider.py — model-agnostic LLM loader.
Change ACTIVE_LLM in .env to switch providers without touching agent code.
"""

import os
from dotenv import load_dotenv

load_dotenv()

ACTIVE_LLM = os.getenv("ACTIVE_LLM", "groq")
MODEL_NAME  = os.getenv("MODEL_NAME", "llama-3.1-8b-instant")


def get_llm():
    """Return a LangChain-compatible LLM based on .env config."""

    if ACTIVE_LLM == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=MODEL_NAME,
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.3,
        )

    elif ACTIVE_LLM == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=MODEL_NAME,
            google_api_key=os.getenv("GEMINI_API_KEY"),
            temperature=0.3,
        )

    elif ACTIVE_LLM == "claude":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=MODEL_NAME or "claude-3-haiku-20240307",
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            temperature=0.3,
        )

    elif ACTIVE_LLM == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=MODEL_NAME or "gpt-3.5-turbo",
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0.3,
        )

    else:
        raise ValueError(f"Unknown ACTIVE_LLM='{ACTIVE_LLM}'. Choose: groq | gemini | claude | openai")


def get_model_info() -> str:
    return f"{ACTIVE_LLM} / {MODEL_NAME}"