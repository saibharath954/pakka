from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    hindsight_url: str
    hindsight_api_key: str | None
    bank_id: str
    llm_base_url: str
    llm_api_key: str | None
    llm_model: str
    offline: bool
    parser: str  # "llm" or "rules"
    company: str = "Sri Venkateswara Agencies"
    city: str = "Secunderabad, Hyderabad"

    @classmethod
    def from_env(cls) -> "Settings":
        llm_key = os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY") or None
        return cls(
            hindsight_url=os.getenv("HINDSIGHT_URL", "https://api.hindsight.vectorize.io"),
            hindsight_api_key=os.getenv("HINDSIGHT_API_KEY") or None,
            bank_id=os.getenv("MUNSHI_BANK_ID", "sri-venkateswara-agencies"),
            llm_base_url=os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1"),
            llm_api_key=llm_key,
            llm_model=os.getenv("LLM_MODEL", "openai/gpt-oss-120b"),
            offline=os.getenv("MUNSHI_OFFLINE", "0").lower() in {"1", "true", "yes"},
            parser=os.getenv("MUNSHI_PARSER", "llm" if llm_key else "rules"),
        )
