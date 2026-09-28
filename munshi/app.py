"""FastAPI app: the order-desk UI and its JSON API.

Run:  uvicorn munshi.app:app --reload     then open http://localhost:8000
"""

from __future__ import annotations

import asyncio
import json
import logging
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .agent import Munshi
from .catalog import BY_CODE, CATALOG
from .config import Settings
from .evaluate import learning_curve
from .llm import OpenAICompatLLM
from .memory import HindsightMemory, LocalMemory
from .seed_data import BY_ID, RETAILERS
from .store import Inbox

log = logging.getLogger("munshi")
STATIC = Path(__file__).parent / "static"
DATA = Path(__file__).parent.parent / "data"
SAMPLE_CURVE = Path(__file__).parent.parent / "docs" / "learning_curve.sample.json"


class NewMessage(BaseModel):
    retailer_id: str
    text: str = Field(min_length=2)


class FinalLine(BaseModel):
    phrase: str | None = None
    sku: str
    units: int = Field(gt=0)
    basis: str = "none"
    suggested: str | None = None


class ConfirmIn(BaseModel):
    lines: list[FinalLine] = Field(min_length=1)


class AskIn(BaseModel):
    question: str = Field(min_length=3)


def build(settings: Settings) -> Munshi:
    if settings.offline:
        memory = LocalMemory()
    else:
        memory = HindsightMemory(settings.hindsight_url, settings.hindsight_api_key, settings.bank_id, settings.company)
    llm = None
    if settings.parser == "llm" and settings.llm_api_key and not settings.offline:
        llm = OpenAICompatLLM(settings.llm_base_url, settings.llm_api_key, settings.llm_model)
    return Munshi(memory, llm, settings.company)


def create_app(agent: Munshi | None = None, settings: Settings | None = None, data_dir: Path | None = DATA) -> FastAPI:
    settings = settings or Settings.from_env()
    curve_path = (data_dir / "learning_curve.json") if data_dir else None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.agent = agent or build(settings)
        app.state.inbox = Inbox(data_dir / "inbox.json" if data_dir else None, app.state.agent.clock)
        app.state.replay = {"running": False, "phase": None, "done": 0, "total": 0, "error": None}
        await app.state.agent.memory.setup()
        yield
        await app.state.agent.memory.close()

    app = FastAPI(title="Munshi", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.exception_handler(Exception)
    async def on_error(request: Request, exc: Exception):
        log.error("request failed: %s\n%s", exc, traceback.format_exc())
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=502)

    def m(request: Request) -> Munshi:
        return request.app.state.agent

    def inbox(request: Request) -> Inbox:
        return request.app.state.inbox

    @app.get("/")
    async def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/api/config")
    async def config(request: Request):
        return {"company": settings.company, "city": settings.city, "bank_id": settings.bank_id,
                "offline": settings.offline, "parser": "llm" if m(request).llm else "rules",
                "model": settings.llm_model if m(request).llm else None}

    @app.get("/api/catalog")
    async def catalog():
        return [{"code": s.code, "name": s.name, "case_qty": s.case_qty, "price": s.price} for s in CATALOG]

    @app.get("/api/retailers")
    async def retailers():
        return [{"id": r.id, "name": r.name, "area": r.area, "owner": r.owner, "style": r.style} for r in RETAILERS]

    @app.get("/api/retailers/{rid}")
    async def retailer(rid: str, request: Request):
        if rid not in BY_ID:
            raise HTTPException(404, "unknown retailer")
        vocab, orders = await asyncio.gather(m(request).vocabulary(rid), m(request).recent_orders(rid))
        return {**vocab, "orders": orders}

    @app.post("/api/retailers/{rid}/dictionary/refresh")
    async def refresh_dictionary(rid: str, request: Request):
        if rid not in BY_ID:
            raise HTTPException(404, "unknown retailer")
        await m(request).memory.ensure_dictionary(rid, BY_ID[rid].name)
        await m(request).memory.refresh_dictionary(rid)
        return {"ok": True}

    @app.get("/api/inbox")
    async def list_inbox(request: Request):
        return inbox(request).all()

    @app.post("/api/inbox")
    async def new_message(body: NewMessage, request: Request):
        if body.retailer_id not in BY_ID:
            raise HTTPException(404, "unknown retailer")
        return inbox(request).add(body.retailer_id, body.text)

    @app.post("/api/inbox/{mid}/parse")
    async def parse(mid: str, request: Request, memory: bool = True):
        msg = inbox(request).get(mid)
        if not msg:
            raise HTTPException(404, "unknown message")
        return await m(request).process(msg["retailer_id"], msg["text"], use_memory=memory)

    @app.post("/api/inbox/{mid}/confirm")
    async def confirm(mid: str, body: ConfirmIn, request: Request):
        msg = inbox(request).get(mid)
        if not msg:
            raise HTTPException(404, "unknown message")
        for ln in body.lines:
            if ln.sku not in BY_CODE:
                raise HTTPException(422, f"unknown SKU {ln.sku}")
        order = await m(request).confirm(msg["retailer_id"], [ln.model_dump() for ln in body.lines])
        inbox(request).mark_posted(mid, order["order_no"], order["total"], order["tally_xml"])
        return order

    @app.get("/api/orders/{order_no}.xml")
    async def order_xml(order_no: str, request: Request):
        xml = inbox(request).xml.get(order_no)
        if not xml:
            raise HTTPException(404, "unknown order")
        return Response(xml, media_type="application/xml",
                        headers={"Content-Disposition": f'attachment; filename="{order_no}.xml"'})

    @app.post("/api/inbox/reset")
    async def reset_inbox(request: Request):
        inbox(request).reset()
        return inbox(request).all()

    @app.get("/api/insights")
    async def insights(request: Request):
        return await m(request).insights()

    @app.post("/api/ask")
    async def ask(body: AskIn, request: Request):
        return await m(request).ask(body.question)

    @app.get("/api/learning")
    async def learning(request: Request):
        state = request.app.state.replay
        for path in (curve_path, SAMPLE_CURVE):
            if path and path.exists():
                return {"curve": json.loads(path.read_text()), "sample": path == SAMPLE_CURVE, "replay": state}
        return {"curve": None, "sample": False, "replay": state}

    @app.post("/api/learning/run")
    async def run_learning(request: Request):
        state = request.app.state.replay
        if state["running"]:
            return state
        agent_ = m(request)
        state.update(running=True, phase="without", done=0, total=0, error=None)

        def progress(phase, i, n):
            state.update(phase=phase, done=i, total=n)

        async def job():
            try:
                await learning_curve(agent_, agent_.clock(), "offline" if settings.offline else "hindsight",
                                     curve_path, progress)
                await agent_.setup_dictionaries()
                for r in RETAILERS:
                    agent_._spawn(agent_.memory.refresh_dictionary(r.id))
            except Exception as err:  # surfaced to the UI
                state["error"] = f"{type(err).__name__}: {err}"
            finally:
                state["running"] = False

        agent_._spawn(job())
        return state

    return app


app = create_app()
