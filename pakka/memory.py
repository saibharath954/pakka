"""The memory layer. Everything Pakka knows about leads lives in Hindsight.

`HindsightMemory` is the real implementation. `LocalMemory` is a small in-process
stand-in with the same interface, used by the test suite and by PAKKA_OFFLINE=1.
It does keyword matching, not what Hindsight does, so treat offline mode as a
wiring check rather than a demo of memory quality.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

PLAYBOOK_ID = "sales-playbook"
PLAYBOOK_QUERY = (
    "Across all past follow-ups with leads, which approaches got replies or conversions and which were "
    "ignored, stalled or lost? Break it down by customer segment (independent house, apartment, commercial) "
    "and by objection (subsidy doubts, price, EMI, RWA approval, timing, language). For each rule give the "
    "evidence: which leads, what happened, and how many times. Finish with the mistakes we must not repeat."
)

RETAIN_MISSION = (
    "This bank is the sales memory of a rooftop-solar installer. Extract facts about each lead: property type, "
    "locality, electricity bill, decision makers and family members, preferred language, objections, promises "
    "and callback dates (resolve relative dates to absolute ones), competitor mentions, and the outcome of every "
    "follow-up approach we tried (replied, ignored, stalled, converted, lost)."
)


def reflect_mission(company: str, city: str) -> str:
    return (
        f"You are the institutional sales memory of {company}, a rooftop-solar installer in {city}, India. "
        "Answer like a senior sales manager who has read every WhatsApp thread: specific, evidence-backed, "
        "short. Name the leads and dates behind every claim. Never invent facts that are not in memory."
    )


@dataclass
class Memory:
    id: str
    text: str
    type: str | None = None
    when: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class Reflection:
    text: str
    memories: list[Memory] = field(default_factory=list)
    structured: dict[str, Any] | None = None


class MemoryStore(Protocol):
    async def setup(self) -> None: ...
    async def retain(self, content: str, *, tags: list[str], when: datetime, context: str,
                     document_id: str | None = None, metadata: dict[str, str] | None = None) -> None: ...
    async def retain_many(self, items: list[dict[str, Any]]) -> None: ...
    async def recall(self, query: str, *, tags: list[str] | None = None, match_all: bool = False,
                     max_tokens: int = 2048, now: datetime | None = None) -> list[Memory]: ...
    async def reflect(self, query: str, *, tags: list[str] | None = None,
                      response_schema: dict[str, Any] | None = None) -> Reflection: ...
    async def playbook(self) -> dict[str, Any]: ...
    async def refresh_playbook(self) -> None: ...
    async def reset(self) -> None: ...
    async def close(self) -> None: ...


def _tag_filter(tags: list[str] | None, match_all: bool) -> dict[str, Any]:
    if not tags:
        return {}
    # *_strict: memories without tags never leak into a lead-scoped query.
    return {"tags": tags, "tags_match": "all_strict" if match_all else "any_strict"}


def _to_memory(r: Any) -> Memory:
    # Recall results and reflect facts are different generated models; read fields defensively.
    when = getattr(r, "occurred_start", None) or getattr(r, "mentioned_at", None)
    return Memory(getattr(r, "id", None) or "", r.text, getattr(r, "type", None), when,
                  list(getattr(r, "tags", None) or []))


class HindsightMemory:
    def __init__(self, base_url: str, api_key: str | None, bank_id: str, company: str, city: str):
        from hindsight_client import Hindsight

        self.client = Hindsight(base_url=base_url, api_key=api_key, timeout=180.0,
                                user_agent="pakka-sales-memory/1.0")
        self.bank_id = bank_id
        self.company = company
        self.city = city

    async def setup(self) -> None:
        # create_bank is create-or-update, so this is safe on every boot.
        await self.client.acreate_bank(
            self.bank_id,
            retain_mission=RETAIN_MISSION,
            reflect_mission=reflect_mission(self.company, self.city),
            enable_observations=True,
        )
        existing = await self.client.alist_mental_models(self.bank_id)
        ids = {m.id for m in (getattr(existing, "items", None) or [])}
        if PLAYBOOK_ID not in ids:
            await self.client.acreate_mental_model(
                self.bank_id,
                id=PLAYBOOK_ID,
                name="Sales playbook: what actually closes",
                source_query=PLAYBOOK_QUERY,
                max_tokens=1200,
                trigger={"refresh_after_consolidation": True},
            )

    async def retain(self, content, *, tags, when, context, document_id=None, metadata=None) -> None:
        await self.client.aretain(
            self.bank_id, content, timestamp=when, context=context,
            document_id=document_id, metadata=metadata, tags=tags,
        )

    async def retain_many(self, items) -> None:
        # Seed replay: batches keep the number of round trips (and extraction calls) sane.
        for start in range(0, len(items), 8):
            await self.client.aretain_batch(self.bank_id, items[start:start + 8])

    async def recall(self, query, *, tags=None, match_all=False, max_tokens=2048, now=None) -> list[Memory]:
        resp = await self.client.arecall(
            self.bank_id, query, max_tokens=max_tokens, budget="mid",
            query_timestamp=now.isoformat() if now else None,
            **_tag_filter(tags, match_all),
        )
        return [_to_memory(r) for r in resp.results]

    async def reflect(self, query, *, tags=None, response_schema=None) -> Reflection:
        resp = await self.client.areflect(
            self.bank_id, query, budget="mid", include_facts=True,
            response_schema=response_schema, **_tag_filter(tags, False),
        )
        used = (resp.based_on.memories or []) if resp.based_on else []
        return Reflection(
            text=resp.text,
            memories=[_to_memory(m) for m in used],
            structured=resp.structured_output,
        )

    async def playbook(self) -> dict[str, Any]:
        try:
            mm = await self.client.aget_mental_model(self.bank_id, PLAYBOOK_ID)
        except Exception:  # not created yet / bank reset
            return {"content": None, "last_refreshed_at": None}
        return {"content": mm.content, "last_refreshed_at": mm.last_refreshed_at, "is_stale": mm.is_stale}

    async def refresh_playbook(self) -> None:
        await self.client.arefresh_mental_model(self.bank_id, PLAYBOOK_ID)

    async def reset(self) -> None:
        try:
            await self.client.adelete_bank(self.bank_id)
        except Exception:
            pass
        await self.setup()

    async def close(self) -> None:
        await self.client.aclose()


class LocalMemory:
    """Keyword-overlap stand-in for tests and offline wiring checks."""

    def __init__(self):
        self.items: list[dict[str, Any]] = []
        self._playbook: str | None = None

    async def setup(self) -> None:
        return None

    async def retain(self, content, *, tags, when, context, document_id=None, metadata=None) -> None:
        self.items.append({"id": str(uuid.uuid4()), "content": content, "tags": list(tags),
                           "timestamp": when, "context": context})

    async def retain_many(self, items) -> None:
        for it in items:
            await self.retain(it["content"], tags=it.get("tags", []), when=it.get("timestamp"),
                              context=it.get("context", ""))

    @staticmethod
    def _words(s: str) -> set[str]:
        return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) > 2}

    def _matches(self, item_tags: list[str], tags: list[str] | None, match_all: bool) -> bool:
        if not tags:
            return True
        hits = [t in item_tags for t in tags]
        return all(hits) if match_all else any(hits)

    async def recall(self, query, *, tags=None, match_all=False, max_tokens=2048, now=None) -> list[Memory]:
        q = self._words(query)
        scored = []
        for it in self.items:
            if not self._matches(it["tags"], tags, match_all):
                continue
            score = len(q & self._words(it["content"]))
            scored.append((score, it))
        scored.sort(key=lambda x: (x[0], x[1]["timestamp"] or datetime.min), reverse=True)
        budget, out = max_tokens * 4, []
        for _, it in scored:
            budget -= len(it["content"])
            if budget < 0:
                break
            ts = it["timestamp"].isoformat() if it["timestamp"] else None
            out.append(Memory(it["id"], it["content"], "world", ts, it["tags"]))
        return out

    async def reflect(self, query, *, tags=None, response_schema=None) -> Reflection:
        mems = await self.recall(query, tags=tags, max_tokens=1500)
        text = "\n".join(f"- {m.text}" for m in mems[:6]) or "No memories yet."
        return Reflection(text=text, memories=mems[:6], structured=None)

    async def playbook(self) -> dict[str, Any]:
        return {"content": self._playbook, "last_refreshed_at": None, "is_stale": False}

    async def refresh_playbook(self) -> None:
        outcomes = [it for it in self.items if "kind:outcome" in it["tags"]]
        self._playbook = "\n".join(f"- {it['content']}" for it in outcomes[-10:]) or None

    async def reset(self) -> None:
        self.items.clear()
        self._playbook = None

    async def close(self) -> None:
        return None
