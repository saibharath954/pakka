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
    company: str = "SunKiran Solar"
    city: str = "Hyderabad"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            hindsight_url=os.getenv("HINDSIGHT_URL", "https://api.hindsight.vectorize.io"),
            hindsight_api_key=os.getenv("HINDSIGHT_API_KEY") or None,
            bank_id=os.getenv("PAKKA_BANK_ID", "sunkiran-solar"),
            llm_base_url=os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1"),
            llm_api_key=os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY") or None,
            llm_model=os.getenv("LLM_MODEL", "openai/gpt-oss-120b"),
            offline=os.getenv("PAKKA_OFFLINE", "0").lower() in {"1", "true", "yes"},
        )
