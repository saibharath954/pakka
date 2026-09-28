"""Runs HindsightMemory against a stub HTTP server speaking the Hindsight REST shapes.

This does not test Hindsight. It tests that our calls through the official
hindsight-client serialize correctly (tags, tag matching, timestamps, triggers,
response schemas) and that we parse the responses we depend on.
"""

import asyncio
import socket
import threading
import time
from datetime import datetime

import uvicorn
from fastapi import FastAPI, Request

from pakka.agent import IST
from pakka.memory import PLAYBOOK_ID, HindsightMemory

CALLS: list[tuple[str, str, dict]] = []
stub = FastAPI()


@stub.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def catch_all(path: str, request: Request):
    body = await request.json() if (await request.body()) else {}
    CALLS.append((request.method, "/" + path, body))
    p = "/" + path
    if p.endswith("/memories") and request.method == "POST":
        return {"success": True, "bank_id": "b", "items_count": len(body.get("items", [])), "async": False}
    if p.endswith("/memories/recall"):
        return {"results": [{"id": "m1", "text": "Srinivas Rao fears subsidy delay", "type": "world",
                             "occurred_start": "2026-08-05T11:00:00+05:30", "tags": ["lead:L01"]}]}
    if p.endswith("/reflect"):
        return {"text": "Call Irfan after 6pm.", "based_on": {"memories": [{"id": "m9", "text": "callback after 6pm"}]},
                "structured_output": {"due": [{"lead_name": "Mohammed Irfan", "due": "today 6pm",
                                               "action": "call", "why": "promised"}]}}
    if p.endswith("/mental-models") and request.method == "GET":
        return {"items": [], "total": 0, "limit": 100, "offset": 0}
    if p.endswith("/mental-models") and request.method == "POST":
        return {"mental_model_id": PLAYBOOK_ID, "operation_id": "op1"}
    if p.endswith(f"/mental-models/{PLAYBOOK_ID}") and request.method == "GET":
        return {"id": PLAYBOOK_ID, "bank_id": "b", "name": "playbook", "content": "## Apartments\n- send RWA NOC first",
                "last_refreshed_at": "2026-09-28T10:00:00Z"}
    if p.endswith("/refresh"):
        return {"operation_id": "op2", "status": "pending"}
    if request.method in ("PUT", "PATCH", "POST") and p.count("/") == 4:  # bank create/update
        return {"bank_id": "b", "name": "b", "mission": "", "disposition": {"skepticism": 3, "literalism": 3, "empathy": 3}}
    return {"success": True}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_hindsight_memory_speaks_the_api():
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(stub, host="127.0.0.1", port=port, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    while not server.started:
        time.sleep(0.05)
    try:
        mem = HindsightMemory(f"http://127.0.0.1:{port}", "key", "sunkiran-solar", "SunKiran Solar", "Hyderabad")

        async def scenario():
            await mem.setup()
            await mem.retain("hello", tags=["lead:L01", "kind:interaction"], when=datetime(2026, 8, 5, 11, tzinfo=IST),
                             context="ctx", document_id="L01-1", metadata={"lead_id": "L01"})
            await mem.retain_many([{"content": f"e{i}", "tags": ["lead:L02"], "timestamp": datetime(2026, 8, 6, tzinfo=IST),
                                    "context": "c", "document_id": f"d{i}", "metadata": {"k": "v"}} for i in range(10)])
            recalled = await mem.recall("subsidy", tags=["lead:L01"])
            refl = await mem.reflect("what is due?", response_schema={"type": "object"})
            pb = await mem.playbook()
            await mem.refresh_playbook()
            await mem.close()
            return recalled, refl, pb

        recalled, refl, pb = asyncio.run(scenario())
    finally:
        server.should_exit = True
        t.join(timeout=5)

    assert recalled[0].text.startswith("Srinivas") and recalled[0].tags == ["lead:L01"]
    assert refl.structured["due"][0]["lead_name"] == "Mohammed Irfan" and refl.memories[0].id == "m9"
    assert pb["content"].startswith("## Apartments")

    posts = {(m, p): b for m, p, b in CALLS}
    mm = next(b for (m, p), b in posts.items() if m == "POST" and p.endswith("/mental-models"))
    assert mm["id"] == PLAYBOOK_ID and mm["trigger"]["refresh_after_consolidation"] is True

    retains = [b for m, p, b in CALLS if m == "POST" and p.endswith("/memories")]
    assert [len(b["items"]) for b in retains] == [1, 8, 2]
    first = retains[0]["items"][0]
    assert first["tags"] == ["lead:L01", "kind:interaction"] and first["timestamp"].startswith("2026-08-05T11:00")

    recall = next(b for m, p, b in CALLS if p.endswith("/memories/recall"))
    assert recall["tags"] == ["lead:L01"] and recall["tags_match"] == "any_strict"

    reflect = next(b for m, p, b in CALLS if p.endswith("/reflect"))
    assert reflect["response_schema"] == {"type": "object"} and reflect["include"]["facts"] is not None
    assert any(p.endswith(f"/mental-models/{PLAYBOOK_ID}/refresh") for m, p, b in CALLS)
