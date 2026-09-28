import asyncio
from datetime import datetime

from fastapi.testclient import TestClient

from munshi.agent import IST, Munshi
from munshi.app import create_app
from munshi.config import Settings
from munshi.evaluate import learning_curve
from munshi.memory import LocalMemory
from munshi.seed_data import LIVE_MESSAGES

NOW = datetime(2026, 9, 28, 12, 0, tzinfo=IST)


def agent():
    return Munshi(LocalMemory(), None, "Sri Venkateswara Agencies", clock=lambda: NOW)


def test_learning_curve_rises_and_never_auto_accepts_wrong_lines():
    a = agent()
    r = asyncio.run(learning_curve(a, NOW, "offline"))
    with_mem = [w["auto_rate"] for w in r["with_memory"]]
    without = [w["auto_rate"] for w in r["without_memory"]]
    assert with_mem[-1] >= 0.9 and with_mem[-1] > with_mem[0] + 0.5
    assert max(without) < 0.4
    assert r["totals"]["with_memory"]["auto_wrong"] == 0
    assert r["totals"]["without_memory"]["auto_wrong"] > 0


def test_same_nickname_means_different_products_for_different_shops():
    a = agent()
    asyncio.run(learning_curve(a, NOW, "offline"))
    sharma = asyncio.run(a.process("R01", "blue wala 1 cartoon"))["lines"][0]
    sairam = asyncio.run(a.process("R06", "blue wala 1 box"))["lines"][0]
    assert (sharma["sku"], sharma["status"]) == ("SURF-EW-1K", "auto")
    assert (sairam["sku"], sairam["status"]) == ("LAYS-MM-52", "auto")


def test_usual_list_is_rebuilt_from_the_last_order():
    a = agent()
    asyncio.run(learning_curve(a, NOW, "offline"))
    p = asyncio.run(a.process("R05", LIVE_MESSAGES[3][1]))
    assert p["repeat"] and sum(1 for x in p["lines"] if x["basis"] == "repeat") >= 3
    off = asyncio.run(a.process("R05", LIVE_MESSAGES[3][1], use_memory=False))
    assert off["lines"][0]["status"] == "unknown"


def test_confirm_retains_order_and_corrections():
    a = agent()
    final = [{"phrase": "blue wala", "sku": "SURF-EW-1K", "units": 24, "basis": "none", "suggested": None},
             {"phrase": "surf", "sku": "SURF-QW-1K", "units": 12, "basis": "guess", "suggested": "SURF-EW-1K"},
             {"phrase": "tata salt", "sku": "TATASALT-1K", "units": 25, "basis": "catalog", "suggested": "TATASALT-1K"}]
    out = asyncio.run(a.confirm("R10", final, refresh=False))
    kinds = [it["tags"] for it in a.memory.items]
    assert any("kind:order" in t for t in kinds)
    assert sum("kind:alias" in t for t in kinds) == 2  # catalog-exact line is not re-taught
    assert any("kind:correction" in t for t in kinds)
    assert "<VOUCHER VCHTYPE=\"Sales Order\"" in out["tally_xml"] and out["total"] > 0


def test_api_end_to_end(tmp_path):
    s = Settings("x", None, "test", "x", None, "x", True, "rules")
    with TestClient(create_app(agent=agent(), settings=s, data_dir=tmp_path)) as c:
        assert c.get("/").status_code == 200
        inbox = c.get("/api/inbox").json()
        assert len(inbox) == len(LIVE_MESSAGES)
        c.post("/api/learning/run")
        for _ in range(200):
            if not c.get("/api/learning").json()["replay"]["running"]:
                break
            asyncio.run(asyncio.sleep(0.05))
        curve = c.get("/api/learning").json()
        assert curve["curve"]["mode"] == "offline" and not curve["sample"]
        mid = next(m["id"] for m in inbox if m["retailer_id"] == "R01")
        parsed = c.post(f"/api/inbox/{mid}/parse?memory=true").json()
        assert all(x["status"] == "auto" for x in parsed["lines"])
        lines = [{"phrase": x["phrase"], "sku": x["sku"], "units": x["units"], "basis": x["basis"]} for x in parsed["lines"]]
        order = c.post(f"/api/inbox/{mid}/confirm", json={"lines": lines}).json()
        assert c.get(f"/api/orders/{order['order_no']}.xml").status_code == 200
        assert c.post(f"/api/inbox/{mid}/confirm", json={"lines": [{"sku": "NOPE", "units": 1}]}).status_code == 422
        vocab = c.get("/api/retailers/R01").json()
        assert any(v["phrase"] == "blue wala" and v["sku"] == "SURF-EW-1K" for v in vocab["vocabulary"])
        assert c.get("/api/retailers/R99").status_code == 404
        new = c.post("/api/inbox", json={"retailer_id": "R06", "text": "blue wala 1 box"}).json()
        assert c.post(f"/api/inbox/{new['id']}/parse").json()["lines"][0]["sku"] == "LAYS-MM-52"
        assert "answer" in c.post("/api/ask", json={"question": "what does blue wala mean?"}).json()


class FakeLLM:
    def __init__(self, reply):
        self.reply, self.prompts = reply, []

    async def json(self, system, user):
        self.prompts.append(user)
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def test_llm_parse_feeds_the_same_evidence_gate():
    llm = FakeLLM({"lines": [{"phrase": "Blue Wala", "qty": 2, "unit": "case", "sku_guess": "SURF-QW-1K"},
                             {"phrase": "tata salt", "qty": 1, "unit": "cartoon", "sku_guess": None}]})
    a = Munshi(LocalMemory(), llm, "x", clock=lambda: NOW)
    p = asyncio.run(a.process("R01", "blue wala 2 cartoon, tata salt 1 cartoon", use_memory=False))
    assert p["parser"] == "llm"
    blue, salt = p["lines"]
    # The LLM's guess is only a suggestion: with no evidence it must go to the operator.
    assert (blue["sku"], blue["status"]) == ("SURF-QW-1K", "review")
    assert (salt["sku"], salt["units"], salt["status"]) == ("TATASALT-1K", 25, "auto")
    assert "CATALOGUE" in llm.prompts[0]


def test_llm_failure_falls_back_to_rules():
    a = Munshi(LocalMemory(), FakeLLM(RuntimeError("bad json")), "x", clock=lambda: NOW)
    p = asyncio.run(a.process("R01", "tata salt 1 cartoon", use_memory=False))
    assert p["parser"] == "rules (fallback)" and p["lines"][0]["sku"] == "TATASALT-1K"
