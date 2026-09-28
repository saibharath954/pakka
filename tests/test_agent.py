import asyncio
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from pakka.agent import IST, Pakka
from pakka.app import create_app
from pakka.config import Settings
from pakka.crm import CRM
from pakka.llm import TemplateLLM, extract_json
from pakka.memory import LocalMemory
from pakka.seed_data import EVENTS, LEADS

NOW = datetime(2026, 9, 28, 12, 0, tzinfo=IST)


class RecordingLLM(TemplateLLM):
    def __init__(self):
        self.prompts = []

    async def json(self, system, user):
        self.prompts.append(user)
        return await super().json(system, user)


def make_agent():
    return Pakka(LocalMemory(), RecordingLLM(), CRM(None), "SunKiran Solar", "Hyderabad", clock=lambda: NOW)


def run(coro):
    return asyncio.run(coro)


def test_seed_data_is_consistent():
    ids = {lead.id for lead in LEADS}
    assert all(e.lead_id in ids for e in EVENTS)
    assert all(e.day <= 0 for e in EVENTS)
    for e in EVENTS:
        if e.kind == "outcome":
            assert e.approach and e.result in {"replied", "ignored", "stalled", "converted", "lost"}


def test_replay_retains_everything_with_lead_and_kind_tags():
    agent = make_agent()
    out = run(agent.replay(until_day=0))
    assert out["retained"] == len(EVENTS)
    items = agent.memory.items
    assert all(any(t.startswith("lead:") for t in it["tags"]) for it in items)
    assert sum("kind:outcome" in it["tags"] for it in items) == sum(e.kind == "outcome" for e in EVENTS)
    # Outcomes drive CRM status; nothing is hard-coded.
    assert agent.crm.get("L01")["status"] == "won"
    assert agent.crm.get("L04")["status"] == "lost"
    assert agent.crm.get("L12")["status"] == "open"


def test_staged_replay_does_not_duplicate():
    agent = make_agent()
    first = run(agent.replay(until_day=-40))["retained"]
    second = run(agent.replay(since_day=-40, until_day=0))["retained"]
    assert first + second == len(EVENTS)
    assert len(agent.memory.items) == len(EVENTS)


def test_lead_recall_is_scoped_to_that_lead():
    agent = make_agent()
    run(agent.replay())
    mems = run(agent.memory.recall("subsidy", tags=["lead:L11"]))
    assert mems and all("lead:L11" in m.tags for m in mems)


def test_draft_without_memory_sees_only_crm_row_and_last_message():
    agent = make_agent()
    run(agent.replay())
    r = run(agent.draft("L12", use_memory=False))
    prompt = agent.llm.prompts[-1]
    assert r["memories"] == [] and not r["playbook_used"]
    assert "[M1]" not in prompt and "[P1]" not in prompt
    assert "LATEST MESSAGE FROM LEAD" in prompt
    assert r["draft"]["approach"] == "discount"


def test_draft_with_memory_injects_lead_history_and_similar_outcomes():
    agent = make_agent()
    run(agent.replay())
    run(agent.memory.refresh_playbook())
    r = run(agent.draft("L12", use_memory=True))
    prompt = agent.llm.prompts[-1]
    assert "[M1]" in prompt and "[P1]" in prompt
    assert "TEAM PLAYBOOK" in prompt
    refs = [m["ref"] for m in r["memories"]]
    assert refs[0] == "M1" and any(ref.startswith("P") for ref in refs)
    # Similar-lead outcomes must not repeat this lead's own memories.
    lead_ids = {m["id"] for m in r["memories"] if m["ref"].startswith("M")}
    assert not lead_ids & {m["id"] for m in r["memories"] if m["ref"].startswith("P")}


def test_log_outcome_updates_status_and_tags():
    agent = make_agent()
    out = run(agent.log_outcome("L12", "rwa_noc_template_plus_society_presentation", "converted", "Signed 3kW."))
    assert "approach:rwa_noc_template_plus_society_presentation" in out["tags"]
    assert agent.crm.get("L12")["status"] == "won"


def test_extract_json_tolerates_fences_and_chatter():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure! Here it is: {"a": {"b": 2}} hope that helps') == {"a": {"b": 2}}
    with pytest.raises(Exception):
        extract_json("no json here")


def test_api_end_to_end_offline():
    agent = make_agent()
    settings = Settings.from_env().__class__(
        hindsight_url="x", hindsight_api_key=None, bank_id="test", llm_base_url="x",
        llm_api_key=None, llm_model="x", offline=True)
    with TestClient(create_app(agent=agent, settings=settings)) as c:
        assert c.get("/").status_code == 200
        assert len(c.get("/api/leads").json()) == len(LEADS)
        assert c.post("/api/replay", json={"reset": True, "until_day": 0}).json()["retained"] == len(EVENTS)
        assert c.post("/api/leads/L12/interactions", json={"text": "Can you come Sunday?"}).status_code == 200
        assert c.post("/api/leads/L12/outcomes", json={"approach": "x_y", "result": "bogus"}).status_code == 422
        assert c.get("/api/leads/L99/brief").status_code == 404
        d = c.post("/api/leads/L12/draft?memory=true").json()
        assert d["draft"]["message"] and d["memories"]
        assert "answer" in c.post("/api/ask", json={"question": "Why do apartment leads go cold?"}).json()
        assert "items" in c.get("/api/due").json()
        new = c.post("/api/leads", json={"name": "Test Lead", "segment": "commercial", "locality": "Ameerpet"}).json()
        assert new["id"] == "L14"
