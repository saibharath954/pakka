"""FastAPI app: the rep-facing UI plus a small JSON API.

Run:  uvicorn pakka.app:app --reload     then open http://localhost:8000
"""

from __future__ import annotations

import logging
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .agent import Pakka
from .config import Settings
from .crm import CRM
from .llm import OpenAICompatLLM, TemplateLLM
from .memory import HindsightMemory, LocalMemory

log = logging.getLogger("pakka")
STATIC = Path(__file__).parent / "static"
DATA = Path(__file__).parent.parent / "data"


class InteractionIn(BaseModel):
    text: str = Field(min_length=3)
    channel: str = "whatsapp"


class OutcomeIn(BaseModel):
    approach: str = Field(min_length=2)
    result: str = Field(pattern="^(replied|ignored|stalled|converted|lost)$")
    text: str = ""


class LeadIn(BaseModel):
    name: str
    segment: str = Field(pattern="^(independent_house|apartment|commercial|farm)$")
    locality: str
    source: str = "Manual"
    phone: str = ""
    monthly_bill_inr: int | None = None


class ReplayIn(BaseModel):
    until_day: int = 0
    since_day: int | None = None
    reset: bool = False


class AskIn(BaseModel):
    question: str = Field(min_length=3)


def build(settings: Settings, crm_path: Path | None = DATA / "crm.json") -> Pakka:
    if settings.offline:
        memory, llm = LocalMemory(), TemplateLLM()
    else:
        if not settings.llm_api_key:
            raise RuntimeError("LLM_API_KEY (or GROQ_API_KEY) is not set. Copy .env.example to .env.")
        memory = HindsightMemory(settings.hindsight_url, settings.hindsight_api_key, settings.bank_id,
                                 settings.company, settings.city)
        llm = OpenAICompatLLM(settings.llm_base_url, settings.llm_api_key, settings.llm_model)
    return Pakka(memory, llm, CRM(crm_path), settings.company, settings.city)


def create_app(agent: Pakka | None = None, settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.agent = agent or build(settings)
        await app.state.agent.memory.setup()
        yield
        await app.state.agent.memory.close()

    app = FastAPI(title="Pakka", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.exception_handler(Exception)
    async def on_error(request: Request, exc: Exception):
        log.error("request failed: %s\n%s", exc, traceback.format_exc())
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=502)

    def pakka(request: Request) -> Pakka:
        return request.app.state.agent

    @app.get("/")
    async def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/api/config")
    async def config():
        return {"company": settings.company, "city": settings.city, "bank_id": settings.bank_id,
                "offline": settings.offline, "model": settings.llm_model,
                "hindsight_url": settings.hindsight_url}

    @app.get("/api/leads")
    async def leads(request: Request):
        return pakka(request).crm.all()

    @app.post("/api/leads")
    async def add_lead(body: LeadIn, request: Request):
        return pakka(request).crm.add(body.model_dump())

    def _lead_or_404(request: Request, lead_id: str):
        try:
            return pakka(request).crm.get(lead_id)
        except KeyError:
            raise HTTPException(404, f"unknown lead {lead_id}")

    @app.post("/api/leads/{lead_id}/interactions")
    async def interaction(lead_id: str, body: InteractionIn, request: Request):
        _lead_or_404(request, lead_id)
        return await pakka(request).log_interaction(lead_id, body.text, body.channel)

    @app.post("/api/leads/{lead_id}/outcomes")
    async def outcome(lead_id: str, body: OutcomeIn, request: Request):
        _lead_or_404(request, lead_id)
        return await pakka(request).log_outcome(lead_id, body.approach, body.result, body.text)

    @app.get("/api/leads/{lead_id}/brief")
    async def brief(lead_id: str, request: Request):
        _lead_or_404(request, lead_id)
        return await pakka(request).brief(lead_id)

    @app.post("/api/leads/{lead_id}/draft")
    async def draft(lead_id: str, request: Request, memory: bool = True, goal: str | None = None):
        _lead_or_404(request, lead_id)
        return await pakka(request).draft(lead_id, use_memory=memory, goal=goal)

    @app.get("/api/due")
    async def due(request: Request):
        return await pakka(request).due()

    @app.post("/api/ask")
    async def ask(body: AskIn, request: Request):
        return await pakka(request).ask(body.question)

    @app.get("/api/playbook")
    async def playbook(request: Request):
        return await pakka(request).memory.playbook()

    @app.post("/api/playbook/refresh")
    async def refresh_playbook(request: Request):
        await pakka(request).memory.refresh_playbook()
        return {"ok": True}

    @app.post("/api/replay")
    async def replay(body: ReplayIn, request: Request):
        agent_ = pakka(request)
        if body.reset:
            await agent_.memory.reset()
            agent_.crm.reset()
        return await agent_.replay(until_day=body.until_day, since_day=body.since_day)

    return app


app = create_app()
