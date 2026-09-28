"""Memory layer. Everything Munshi learns lives in Hindsight.

`HindsightMemory` is the real implementation. `LocalMemory` is a keyword-matching
stand-in with the same interface, used by tests and MUNSHI_OFFLINE=1. It exists
so the pipeline can be exercised without network access. It is not a model of
Hindsight's retrieval quality.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Protocol

RETAIN_MISSION = (
    "This bank is the order desk of an FMCG distributor. Retailers send orders on WhatsApp using their own "
    "nicknames for products. Preserve retailer names, retailer ids (like R01), the exact phrase the retailer "
    "wrote (in quotes) and SKU codes (like SURF-EW-1K) verbatim in every fact. Record which SKU a phrase meant "
    "for which retailer, quantities, order dates and weekdays, and corrections made by the operator."
)

OBSERVATIONS_MISSION = (
    "Consolidate per retailer: which phrase means which SKU (with how many confirmations), usual order "
    "contents and quantities, which weekday they order on, and any phrase whose meaning was corrected."
)


def reflect_mission(company: str) -> str:
    return (f"You are the order-desk memory of {company}, an FMCG distributor in Hyderabad. Answer like the "
            "senior order clerk who has handled every retailer for years: short, specific, name the retailer, "
            "the phrase, the SKU code and the dates behind each claim. Never invent products or orders.")


def dictionary_query(name: str, rid: str) -> str:
    return (f"Ordering dictionary for {name} ({rid}): list every phrase or nickname this retailer uses and the "
            "SKU code it means, with how many times it was confirmed; their usual items and quantities; which "
            "weekday they usually order; and any phrase that was corrected. Use a compact markdown list.")


@dataclass
class Memory:
    id: str
    text: str
    type: str | None = None
    when: str | None = None
    tags: list[str] = field(default_factory=list)
    document_id: str | None = None
    chunk: str | None = None  # the raw retained text this fact came from
    source_count: int = 0  # observations: how many facts support it

    @property
    def raw(self) -> str:
        return self.chunk or self.text


@dataclass
class Reflection:
    text: str
    memories: list[Memory] = field(default_factory=list)
    structured: dict[str, Any] | None = None


class MemoryStore(Protocol):
    async def setup(self) -> None: ...
    async def retain_many(self, items: list[dict[str, Any]]) -> None: ...
    async def recall(self, query: str, *, tags: list[str] | None = None, match_all: bool = False,
                     max_tokens: int = 3000, window_days: int | None = None,
                     now: datetime | None = None) -> list[Memory]: ...
    async def reflect(self, query: str, *, tags: list[str] | None = None,
                      response_schema: dict[str, Any] | None = None) -> Reflection: ...
    async def ensure_dictionary(self, rid: str, name: str) -> None: ...
    async def dictionary(self, rid: str) -> dict[str, Any]: ...
    async def refresh_dictionary(self, rid: str) -> None: ...
    async def reset(self) -> None: ...
    async def close(self) -> None: ...


def _dict_id(rid: str) -> str:
    return f"dictionary-{rid.lower()}"


def _tag_filter(tags: list[str] | None, match_all: bool) -> dict[str, Any]:
    if not tags:
        return {}
    return {"tags": tags, "tags_match": "all_strict" if match_all else "any_strict"}


def _to_memory(r: Any, chunks: dict[str, Any] | None = None) -> Memory:
    chunk_id = getattr(r, "chunk_id", None)
    chunk = chunks.get(chunk_id) if (chunks and chunk_id) else None
    return Memory(
        id=getattr(r, "id", None) or "",
        text=r.text,
        type=getattr(r, "type", None),
        when=getattr(r, "occurred_start", None) or getattr(r, "mentioned_at", None),
        tags=list(getattr(r, "tags", None) or []),
        document_id=getattr(r, "document_id", None),
        chunk=getattr(chunk, "text", None) if chunk is not None else None,
        source_count=len(getattr(r, "source_fact_ids", None) or []),
    )


class HindsightMemory:
    def __init__(self, base_url: str, api_key: str | None, bank_id: str, company: str):
        from hindsight_client import Hindsight

        self.client = Hindsight(base_url=base_url, api_key=api_key, timeout=180.0,
                                user_agent="munshi-order-desk/1.0")
        self.bank_id = bank_id
        self.company = company
        self._dicts: set[str] = set()

    async def setup(self) -> None:
        await self.client.acreate_bank(
            self.bank_id,
            retain_mission=RETAIN_MISSION,
            observations_mission=OBSERVATIONS_MISSION,
            reflect_mission=reflect_mission(self.company),
            enable_observations=True,
        )
        existing = await self.client.alist_mental_models(self.bank_id)
        self._dicts = {m.id for m in (getattr(existing, "items", None) or [])}

    async def retain_many(self, items: list[dict[str, Any]]) -> None:
        for start in range(0, len(items), 16):
            await self.client.aretain_batch(self.bank_id, items[start:start + 16])

    async def recall(self, query, *, tags=None, match_all=False, max_tokens=3000, window_days=None, now=None):
        kwargs: dict[str, Any] = {}
        if window_days and now:
            kwargs["temporal_window"] = {"start": (now - timedelta(days=window_days)).isoformat(), "end": now.isoformat()}
        resp = await self.client.arecall(
            self.bank_id, query, max_tokens=max_tokens, budget="mid",
            query_timestamp=now.isoformat() if now else None,
            include_chunks=True, max_chunk_tokens=4000,
            **_tag_filter(tags, match_all), **kwargs,
        )
        return [_to_memory(r, resp.chunks) for r in resp.results]

    async def reflect(self, query, *, tags=None, response_schema=None) -> Reflection:
        resp = await self.client.areflect(self.bank_id, query, budget="mid", include_facts=True,
                                          response_schema=response_schema, **_tag_filter(tags, False))
        used = (resp.based_on.memories or []) if resp.based_on else []
        return Reflection(resp.text, [_to_memory(m) for m in used], resp.structured_output)

    async def ensure_dictionary(self, rid: str, name: str) -> None:
        if _dict_id(rid) in self._dicts:
            return
        await self.client.acreate_mental_model(
            self.bank_id, id=_dict_id(rid), name=f"{name}: ordering dictionary",
            source_query=dictionary_query(name, rid), tags=[f"retailer:{rid}"], max_tokens=700,
            trigger={"refresh_after_consolidation": True},
        )
        self._dicts.add(_dict_id(rid))

    async def dictionary(self, rid: str) -> dict[str, Any]:
        try:
            mm = await self.client.aget_mental_model(self.bank_id, _dict_id(rid))
        except Exception:
            return {"content": None, "last_refreshed_at": None}
        return {"content": mm.content, "last_refreshed_at": mm.last_refreshed_at}

    async def refresh_dictionary(self, rid: str) -> None:
        await self.client.arefresh_mental_model(self.bank_id, _dict_id(rid))

    async def reset(self) -> None:
        try:
            await self.client.adelete_bank(self.bank_id)
        except Exception:
            pass
        self._dicts.clear()
        await self.setup()

    async def close(self) -> None:
        await self.client.aclose()


class LocalMemory:
    """In-process stand-in: keyword overlap, strict tags, time window. No consolidation."""

    def __init__(self):
        self.items: list[dict[str, Any]] = []
        self.dicts: dict[str, str] = {}

    async def setup(self) -> None:
        return None

    async def retain_many(self, items) -> None:
        for it in items:
            self.items.append({"id": str(uuid.uuid4()), **it})

    @staticmethod
    def _words(s: str) -> set[str]:
        return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) > 1}

    async def recall(self, query, *, tags=None, match_all=False, max_tokens=3000, window_days=None, now=None):
        q = self._words(query)
        out = []
        for it in self.items:
            if tags:
                hits = [t in it.get("tags", []) for t in tags]
                if not (all(hits) if match_all else any(hits)):
                    continue
            ts = it.get("timestamp")
            if window_days and now and ts and not (now - timedelta(days=window_days) <= ts <= now):
                continue
            if now and ts and ts > now:
                continue
            score = len(q & self._words(it["content"]))
            out.append((score, ts or datetime.min, it))
        out.sort(key=lambda x: (x[0], x[1]), reverse=True)
        budget, mems = max_tokens * 4, []
        for _, _, it in out:
            budget -= len(it["content"])
            if budget < 0:
                break
            mems.append(Memory(it["id"], it["content"], "world",
                               it["timestamp"].isoformat() if it.get("timestamp") else None,
                               list(it.get("tags", [])), it.get("document_id"), it["content"]))
        return mems

    async def reflect(self, query, *, tags=None, response_schema=None) -> Reflection:
        mems = await self.recall(query, tags=tags, max_tokens=1200)
        return Reflection("\n".join(f"- {m.text}" for m in mems[:8]) or "Nothing in memory yet.", mems[:8], None)

    async def ensure_dictionary(self, rid: str, name: str) -> None:
        self.dicts.setdefault(rid, "")

    async def dictionary(self, rid: str) -> dict[str, Any]:
        return {"content": self.dicts.get(rid) or None, "last_refreshed_at": None}

    async def refresh_dictionary(self, rid: str) -> None:
        facts = [it["content"] for it in self.items
                 if f"retailer:{rid}" in it.get("tags", []) and "kind:alias" in it.get("tags", [])]
        self.dicts[rid] = "\n".join(f"- {f}" for f in facts[-12:])

    async def reset(self) -> None:
        self.items.clear()
        self.dicts.clear()

    async def close(self) -> None:
        return None
