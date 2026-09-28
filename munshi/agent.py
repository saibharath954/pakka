"""Munshi's order desk: parse, recall, gate, confirm, retain.

The loop for every WhatsApp message:

1. recall what memory knows about this retailer (strictly scoped by tag);
2. parse the message into (phrase, qty, unit) lines, with the LLM or the rule parser;
3. resolve each phrase from *evidence*: confirmations recalled from memory, or an
   unambiguous item-master match. A nickname auto-accepts only after it has been
   confirmed at least twice for this retailer;
4. the operator fixes whatever is left and confirms;
5. the confirmed order, plus one confirmation fact per nickname, is retained.

Step 5 is the whole learning loop. There are no hand-written alias tables anywhere.
"""

from __future__ import annotations

import asyncio
import re
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from .catalog import BY_CODE, catalog_prompt
from .llm import OpenAICompatLLM
from .memory import MemoryStore
from .parser import Line, RawLine, alias_evidence, is_repeat, last_order, norm, resolve, rule_parse, unit_of
from .seed_data import BY_ID, RETAILERS
from .tally import sales_order_xml

IST = timezone(timedelta(hours=5, minutes=30))

PARSE_SYSTEM = """You read WhatsApp orders sent by kirana shops to an FMCG distributor in Hyderabad.
Messages mix English, Hindi, Telugu and Urdu, and use shop-specific nicknames for products.
Split the message into order lines. For each line return the product phrase EXACTLY as the shop wrote it
(lowercase, without the quantity or unit words), the quantity, and the unit.
Units: "case" for cartoon/carton/box/peti/dabba/cs/case; "dozen" for dozen; otherwise "pcs".
Ignore greetings, delivery requests and phrases like "same as last time" / "usual list" (those are handled separately).
If memory or the catalogue makes the SKU clear, put its code in "sku_guess", else null.

Return JSON: {"lines": [{"phrase": str, "qty": int, "unit": "case"|"dozen"|"pcs", "sku_guess": str|null}]}"""

INSIGHT_SCHEMA = {
    "type": "object",
    "properties": {
        "insights": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "retailer": {"type": "string"},
                    "kind": {"type": "string", "enum": ["overdue", "pattern", "risk"]},
                    "headline": {"type": "string"},
                    "detail": {"type": "string"},
                },
                "required": ["retailer", "kind", "headline", "detail"],
            },
        }
    },
    "required": ["insights"],
}


def _retailer(rid: str):
    if rid not in BY_ID:
        raise KeyError(rid)
    return BY_ID[rid]


def _mem(m) -> dict[str, Any]:
    return {"id": m.id, "text": m.text, "type": m.type, "when": m.when, "sources": m.source_count}


def alias_fact(r, phrase: str, sku: str, when: datetime, suggested: str | None = None) -> str:
    name = BY_CODE[sku].name
    if suggested and suggested != sku:
        return (f'Order-desk correction: {r.name} ({r.id}) wrote "{phrase}". Munshi suggested {suggested}, '
                f"but the operator confirmed it meant {sku} ({name}). Date {when:%Y-%m-%d}.")
    return f'Order-desk confirmation: {r.name} ({r.id}) wrote "{phrase}" and it meant {sku} ({name}). Date {when:%Y-%m-%d}.'


def order_fact(order_no: str, r, when: datetime, lines: dict[str, int]) -> str:
    body = "; ".join(f"{code} x {units}" for code, units in lines.items())
    return f"Confirmed order {order_no} from {r.name} ({r.id}) on {when:%Y-%m-%d} ({when:%A}): {body}"


class Munshi:
    def __init__(self, memory: MemoryStore, llm: OpenAICompatLLM | None, company: str,
                 clock: Callable[[], datetime] | None = None):
        self.memory = memory
        self.llm = llm
        self.company = company
        self.clock = clock or (lambda: datetime.now(IST))
        self._bg: set[asyncio.Task] = set()

    # ------------------------------------------------------------------ parse

    async def _raw_lines(self, text: str, context: str) -> tuple[list[RawLine], dict[str, str], str]:
        if self.llm is None:
            return rule_parse(text), {}, "rules"
        user = f"CATALOGUE (code | name | case size):\n{catalog_prompt()}\n\n{context}\n\nMESSAGE:\n{text}"
        try:
            out = await self.llm.json(PARSE_SYSTEM, user)
            raw, guesses = [], {}
            for ln in out.get("lines", []):
                phrase, qty = norm(str(ln.get("phrase", ""))), int(ln.get("qty") or 0)
                if not phrase or qty <= 0 or is_repeat(phrase):
                    continue
                raw.append(RawLine(phrase, qty, unit_of(ln.get("unit")) if ln.get("unit") not in ("case", "dozen", "pcs")
                                   else ln["unit"]))
                if ln.get("sku_guess") in BY_CODE:
                    guesses[phrase] = ln["sku_guess"]
            if raw or not rule_parse(text):
                return raw, guesses, "llm"
        except Exception:
            pass  # malformed output or provider error: fall back rather than fail the order
        return rule_parse(text), {}, "rules (fallback)"

    async def process(self, rid: str, text: str, when: datetime | None = None, use_memory: bool = True) -> dict:
        r = _retailer(rid)
        now = when or self.clock()
        memories, order_mems = [], []
        if use_memory:
            memories = await self.memory.recall(f"{r.name} ({r.id}) order phrases: {text}",
                                                tags=[f"retailer:{rid}"], max_tokens=4000, now=now)
        repeat = is_repeat(text)
        if use_memory and repeat:
            order_mems = await self.memory.recall(f"most recent confirmed order from {r.name}",
                                                  tags=[f"retailer:{rid}", "kind:order"], match_all=True,
                                                  max_tokens=2500, window_days=35, now=now)

        evidence = alias_evidence(memories) if use_memory else None
        known = "; ".join(f'"{p}" = {max(v.values(), key=lambda e: e.confirmations).sku}'
                          for p, v in (evidence or {}).items())
        context = f"RETAILER: {r.name} ({r.id}), {r.area}\nKNOWN NICKNAMES FROM MEMORY: {known or 'none'}"
        raw, guesses, parser = await self._raw_lines(text, context)

        lines: list[Line] = []
        repeat_info = None
        if repeat:
            oid, odate, olines, mid = last_order(order_mems)
            if olines:
                repeat_info = {"order_no": oid, "date": odate}
                for code, units in olines.items():
                    lines.append(Line(f"(last order {odate})", units, "pcs", code, units, "auto", "repeat",
                                      memory_ids=[mid] if mid else [], note=f"repeated from {oid} on {odate}"))
            else:
                lines.append(Line("same as last time", 0, "pcs", None, 0, "unknown", "none",
                                  note="no memory of a previous order"))
        lines += [resolve(x, evidence, guesses.get(x.phrase)) for x in raw]

        observations = [m for m in memories if m.type == "observation"][:4]
        return {
            "retailer": {"id": r.id, "name": r.name, "area": r.area, "owner": r.owner},
            "text": text,
            "received_at": now.isoformat(),
            "use_memory": use_memory,
            "parser": parser,
            "repeat": repeat_info,
            "lines": [asdict(x) for x in lines],
            "stats": {
                "auto": sum(x.status == "auto" for x in lines),
                "review": sum(x.status != "auto" for x in lines),
                "memories_recalled": len(memories) + len(order_mems),
            },
            "evidence_memories": [_mem(m) for m in memories if any(m.id in x.memory_ids for x in lines)][:12]
                                 + [_mem(m) for m in order_mems if any(m.id in x.memory_ids for x in lines)][:2],
            "observations": [_mem(m) for m in observations],
        }

    # ------------------------------------------------------------------ confirm (the learning step)

    def confirm_items(self, rid: str, final: list[dict], when: datetime, order_no: str) -> tuple[list[dict], dict[str, int]]:
        """Memory items for a confirmed order. `final` lines carry phrase, sku, units, basis, suggested."""
        r = _retailer(rid)
        merged: dict[str, int] = {}
        for ln in final:
            if ln.get("sku") and ln.get("units", 0) > 0:
                merged[ln["sku"]] = merged.get(ln["sku"], 0) + int(ln["units"])
        items = [{
            "content": order_fact(order_no, r, when, merged),
            "tags": [f"retailer:{rid}", "kind:order"],
            "timestamp": when, "context": "confirmed WhatsApp order",
            "document_id": f"order-{order_no}", "metadata": {"retailer": rid, "order_no": order_no},
        }]
        for ln in final:
            phrase, sku = ln.get("phrase"), ln.get("sku")
            if not phrase or not sku or ln.get("basis") == "repeat":
                continue
            corrected = ln.get("suggested") and ln["suggested"] != sku
            if ln.get("basis") == "catalog" and not corrected:
                continue  # the item master already knows this one
            items.append({
                "content": alias_fact(r, phrase, sku, when, ln.get("suggested")),
                "tags": [f"retailer:{rid}", "kind:alias", f"sku:{sku}"] + (["kind:correction"] if corrected else []),
                "timestamp": when, "context": "operator confirmed what a retailer's phrase means",
                "document_id": f"alias-{order_no}-{norm(phrase).replace(' ', '-')}",
                "metadata": {"retailer": rid, "phrase": norm(phrase), "sku": sku},
            })
        return items, merged

    async def confirm(self, rid: str, final: list[dict], when: datetime | None = None,
                      refresh: bool = True) -> dict:
        r = _retailer(rid)
        when = when or self.clock()
        order_no = f"SO-{when:%y%m%d}-{uuid.uuid4().hex[:4].upper()}"
        items, merged = self.confirm_items(rid, final, when, order_no)
        await self.memory.retain_many(items)
        if refresh:
            self._spawn(self._refresh_dictionary(rid))
        lines = [{"sku": k, "units": v} for k, v in merged.items()]
        return {
            "order_no": order_no,
            "retailer": r.name,
            "lines": [{**ln, "name": BY_CODE[ln["sku"]].name, "amount": round(BY_CODE[ln["sku"]].price * ln["units"], 2)}
                      for ln in lines],
            "total": round(sum(BY_CODE[k].price * v for k, v in merged.items()), 2),
            "retained": [it["content"] for it in items],
            "tally_xml": sales_order_xml(order_no, r.name, when, lines),
        }

    async def _refresh_dictionary(self, rid: str) -> None:
        r = _retailer(rid)
        await self.memory.ensure_dictionary(rid, r.name)
        await self.memory.refresh_dictionary(rid)

    def _spawn(self, coro) -> None:
        task = asyncio.ensure_future(coro)
        self._bg.add(task)
        task.add_done_callback(self._bg.discard)

    # ------------------------------------------------------------------ what Munshi knows

    async def vocabulary(self, rid: str) -> dict:
        r = _retailer(rid)
        mems = await self.memory.recall(f"phrases and nicknames {r.name} uses for products",
                                        tags=[f"retailer:{rid}", "kind:alias"], match_all=True, max_tokens=8000,
                                        now=self.clock())
        ev = alias_evidence(mems)
        rows = []
        for phrase, cands in ev.items():
            best = max(cands.values(), key=lambda e: e.confirmations)
            rows.append({"phrase": phrase, "sku": best.sku, "name": BY_CODE[best.sku].name,
                         "confirmations": best.confirmations, "last_seen": max(best.dates) if best.dates else None,
                         "conflicts": [c.sku for c in cands.values() if c.sku != best.sku],
                         "status": "auto" if best.confirmations >= 2 else "learning"})
        rows.sort(key=lambda x: (-x["confirmations"], x["phrase"]))
        return {"retailer": {"id": r.id, "name": r.name, "area": r.area, "owner": r.owner, "style": r.style},
                "vocabulary": rows, "dictionary": await self.memory.dictionary(rid)}

    async def recent_orders(self, rid: str, limit: int = 6) -> list[dict]:
        r = _retailer(rid)
        mems = await self.memory.recall(f"confirmed orders from {r.name}", tags=[f"retailer:{rid}", "kind:order"],
                                        match_all=True, max_tokens=4000, window_days=60, now=self.clock())
        seen, out = set(), []
        for m in mems:
            for om in re.finditer(r"Confirmed order (\S+) from .+? on (\d{4}-\d{2}-\d{2})[^:]*:([^\n]*)", m.raw):
                if om.group(1) in seen:
                    continue
                seen.add(om.group(1))
                out.append({"order_no": om.group(1), "date": om.group(2), "lines": om.group(3).strip()})
        out.sort(key=lambda o: o["date"], reverse=True)
        return out[:limit]

    async def insights(self) -> dict:
        now = self.clock()
        r = await self.memory.reflect(
            f"Today is {now:%A %d %B %Y}. Looking at every retailer's confirmed orders: (1) which retailers usually "
            "order on a particular weekday and are now overdue, (2) notable ordering patterns (usual quantities, "
            "growing or shrinking orders), (3) risks such as a nickname whose meaning was corrected. At most 6 items, "
            "most actionable first. Name the retailer, dates and SKU codes.",
            response_schema=INSIGHT_SCHEMA,
        )
        items = (r.structured or {}).get("insights") if r.structured else None
        return {"items": items or [], "text": None if items else r.text, "memories": [_mem(m) for m in r.memories][:10]}

    async def ask(self, question: str) -> dict:
        r = await self.memory.reflect(f"Today is {self.clock():%A %d %B %Y}. {question}")
        return {"answer": r.text, "memories": [_mem(m) for m in r.memories][:10]}

    async def setup_dictionaries(self) -> None:
        for r in RETAILERS:
            await self.memory.ensure_dictionary(r.id, r.name)

