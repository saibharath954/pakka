"""Drive HindsightMemory through the official hindsight-client against a stub server.

This does not test Hindsight. It checks that Munshi's calls serialize the way we
rely on (strict tags, chunks, time windows, mental-model tags and triggers,
reflect schemas) and that we read back the fields the evidence gate depends on.
"""

import asyncio
import socket
import threading
import time
from datetime import datetime

import uvicorn
from fastapi import FastAPI, Request

from munshi.agent import IST
from munshi.memory import HindsightMemory
from munshi.parser import alias_evidence

CALLS: list[tuple[str, str, dict]] = []
stub = FastAPI()
CHUNK = 'Order-desk confirmation: Sharma Kirana (R01) wrote "blue wala" and it meant SURF-EW-1K (Surf Excel Easy Wash 1kg). Date 2026-09-01.'


@stub.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def catch_all(path: str, request: Request):
    body = await request.json() if (await request.body()) else {}
    CALLS.append((request.method, "/" + path, body))
    p = "/" + path
    if p.endswith("/memories") and request.method == "POST":
        return {"success": True, "bank_id": "b", "items_count": len(body.get("items", [])), "async": False}
    if p.endswith("/memories/recall"):
        return {"results": [
                    {"id": "f1", "text": "Sharma Kirana calls Surf Excel Easy Wash 'blue wala'", "type": "world",
                     "occurred_start": "2026-09-01T11:00:00+05:30", "tags": ["retailer:R01"], "chunk_id": "c1", "document_id": "d1"},
                    {"id": "o1", "text": "'blue wala' = SURF-EW-1K for Sharma Kirana (3 confirmations)", "type": "observation",
                     "source_fact_ids": ["f1", "f2", "f3"]}],
                "chunks": {"c1": {"id": "c1", "text": CHUNK, "chunk_index": 0}}}
    if p.endswith("/reflect"):
        return {"text": "Hussaini Traders is overdue.", "structured_output": {"insights": []}}
    if p.endswith("/mental-models") and request.method == "GET":
        return {"items": [{"id": "dictionary-r02", "bank_id": "b", "name": "x"}], "total": 1, "limit": 100, "offset": 0}
    if p.endswith("/mental-models") and request.method == "POST":
        return {"mental_model_id": body.get("id"), "operation_id": "op1"}
    if "/mental-models/dictionary-" in p and p.endswith("/refresh"):
        return {"operation_id": "op2", "status": "pending"}
    if "/mental-models/dictionary-" in p:
        return {"id": "dictionary-r01", "bank_id": "b", "name": "d", "content": "- blue wala = SURF-EW-1K"}
    if request.method in ("PUT", "PATCH", "POST") and p.count("/") == 4:
        return {"bank_id": "b", "name": "b", "mission": "", "disposition": {"skepticism": 3, "literalism": 3, "empathy": 3}}
    return {"success": True}


def _port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_hindsight_memory_wire_contract():
    port = _port()
    server = uvicorn.Server(uvicorn.Config(stub, host="127.0.0.1", port=port, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    while not server.started:
        time.sleep(0.05)
    now = datetime(2026, 9, 28, 12, tzinfo=IST)
    try:
        mem = HindsightMemory(f"http://127.0.0.1:{port}", "key", "sva", "Sri Venkateswara Agencies")

        async def scenario():
            await mem.setup()
            await mem.retain_many([{"content": f"c{i}", "tags": ["retailer:R01", "kind:alias"], "timestamp": now,
                                    "context": "x", "document_id": f"d{i}", "metadata": {"k": "v"}} for i in range(20)])
            recalled = await mem.recall("blue wala", tags=["retailer:R01", "kind:order"], match_all=True,
                                        window_days=35, now=now)
            refl = await mem.reflect("who is overdue?", response_schema={"type": "object"})
            await mem.ensure_dictionary("R01", "Sharma Kirana")
            await mem.ensure_dictionary("R02", "Lakshmi General Stores")  # already exists: no create
            d = await mem.dictionary("R01")
            await mem.refresh_dictionary("R01")
            await mem.close()
            return recalled, refl, d

        recalled, refl, d = asyncio.run(scenario())
    finally:
        server.should_exit = True
        t.join(timeout=5)

    assert recalled[0].chunk == CHUNK and recalled[0].document_id == "d1"
    assert recalled[1].type == "observation" and recalled[1].source_count == 3
    assert alias_evidence(recalled)["blue wala"]["SURF-EW-1K"].confirmations == 1
    assert refl.structured == {"insights": []} and d["content"].startswith("- blue wala")

    bank = next(b for m, p, b in CALLS if m in ("PUT", "PATCH") and p.count("/") == 4)
    assert "observations_mission" in str(bank) and "retain_mission" in str(bank)
    assert [len(b["items"]) for m, p, b in CALLS if p.endswith("/memories") and m == "POST"] == [16, 4]
    recall = next(b for m, p, b in CALLS if p.endswith("/memories/recall"))
    assert recall["tags"] == ["retailer:R01", "kind:order"] and recall["tags_match"] == "all_strict"
    assert recall["include"]["chunks"] is not None and recall["temporal_window"]["start"].startswith("2026-08-24")
    creates = [b for m, p, b in CALLS if m == "POST" and p.endswith("/mental-models")]
    assert len(creates) == 1 and creates[0]["id"] == "dictionary-r01" and creates[0]["tags"] == ["retailer:R01"]
    assert creates[0]["trigger"]["refresh_after_consolidation"] is True
    assert any(p.endswith("/mental-models/dictionary-r01/refresh") for m, p, b in CALLS)
