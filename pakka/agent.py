"""Pakka's orchestration: when to retain, what to recall, and how memory reaches the prompt."""

from __future__ import annotations

import asyncio
import zlib
from datetime import datetime, time, timedelta, timezone
from typing import Any, Callable

from .crm import CRM, SEGMENT_LABELS, lead_card
from .llm import LLM
from .memory import Memory, MemoryStore
from .seed_data import Event, events_until

IST = timezone(timedelta(hours=5, minutes=30))

DRAFT_SYSTEM = """You write WhatsApp follow-up messages for the sales team of {company}, a rooftop-solar installer in {city}, India.
Write like a helpful local salesperson, not a marketer: short, specific, respectful ("garu"/"ji" where natural), no emojis spam.
If the lead prefers Telugu, write the message in Telugu script with an English line after it for the rep.
Use ONLY facts given to you. If memory says an approach failed with similar leads, do not use it.

Return one JSON object with keys:
  "message":   the WhatsApp message to send (string)
  "language":  language of the message (string)
  "approach":  a snake_case name for the angle you chose (string)
  "send_at":   when to send it and why, e.g. "today after 7pm, salaried lead" (string)
  "reasoning": 2-5 short bullets explaining the choice; cite memory ids like [M2] or [P1] (list of strings)
  "avoid":     things you deliberately did NOT do and why, citing memory ids (list of strings)"""

DUE_SCHEMA = {
    "type": "object",
    "properties": {
        "due": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "lead_name": {"type": "string"},
                    "due": {"type": "string", "description": "the promised date/time, absolute"},
                    "action": {"type": "string"},
                    "why": {"type": "string"},
                },
                "required": ["lead_name", "due", "action", "why"],
            },
        }
    },
    "required": ["due"],
}


def _mem_dict(m: Memory, ref: str) -> dict[str, Any]:
    return {"ref": ref, "id": m.id, "text": m.text, "type": m.type, "when": m.when, "tags": m.tags}


def _fmt(memories: list[Memory], prefix: str) -> str:
    lines = []
    for i, m in enumerate(memories, 1):
        when = f" ({m.when[:10]})" if m.when else ""
        lines.append(f"[{prefix}{i}]{when} {m.text}")
    return "\n".join(lines)


class Pakka:
    def __init__(self, memory: MemoryStore, llm: LLM, crm: CRM, company: str, city: str,
                 clock: Callable[[], datetime] | None = None):
        self.memory = memory
        self.llm = llm
        self.crm = crm
        self.company = company
        self.city = city
        self.clock = clock or (lambda: datetime.now(IST))
        self._bg: set[asyncio.Task] = set()

    # ------------------------------------------------------------------ retain

    def _tags(self, row: dict[str, Any], kind: str, extra: list[str] | None = None) -> list[str]:
        return [f"lead:{row['id']}", f"segment:{row['segment']}", f"kind:{kind}", *(extra or [])]

    async def log_interaction(self, lead_id: str, text: str, channel: str = "whatsapp",
                              when: datetime | None = None) -> dict[str, Any]:
        row = self.crm.get(lead_id)
        when = when or self.clock()
        content = f"{channel.title()} with {row['name']} ({SEGMENT_LABELS[row['segment']]}, {row['locality']}): {text}"
        await self.memory.retain(
            content, tags=self._tags(row, "interaction", [f"channel:{channel}"]), when=when,
            context=f"sales conversation with a solar lead via {channel}",
            document_id=f"{lead_id}-{when:%Y%m%d%H%M%S}",
            metadata={"lead_id": lead_id, "channel": channel},
        )
        self.crm.touch(lead_id, message=text, when=when.isoformat())
        return {"retained": content, "tags": self._tags(row, "interaction", [f"channel:{channel}"])}

    async def log_outcome(self, lead_id: str, approach: str, result: str, text: str,
                          when: datetime | None = None, refresh: bool = True) -> dict[str, Any]:
        row = self.crm.get(lead_id)
        when = when or self.clock()
        content = (f"Follow-up outcome for {row['name']} ({SEGMENT_LABELS[row['segment']]}, {row['locality']}). "
                   f"Approach tried: {approach.replace('_', ' ')}. Result: {result}. {text}")
        tags = self._tags(row, "outcome", [f"approach:{approach}", f"result:{result}"])
        await self.memory.retain(
            content, tags=tags, when=when, context="result of a sales follow-up approach",
            document_id=f"{lead_id}-outcome-{when:%Y%m%d%H%M%S}",
            metadata={"lead_id": lead_id, "approach": approach, "result": result},
        )
        status = {"converted": "won", "lost": "lost"}.get(result)
        self.crm.touch(lead_id, when=when.isoformat(), status=status)
        if refresh:
            self._spawn(self.memory.refresh_playbook())
        return {"retained": content, "tags": tags}

    def _spawn(self, coro) -> None:
        # The playbook refresh runs server-side and can take a while; never block the rep on it.
        task = asyncio.ensure_future(coro)
        self._bg.add(task)
        task.add_done_callback(self._bg.discard)

    # ------------------------------------------------------------------ recall

    async def brief(self, lead_id: str) -> dict[str, Any]:
        row = self.crm.get(lead_id)
        today = self.clock().strftime("%A %d %B %Y")
        r = await self.memory.reflect(
            f"Today is {today}. Brief me before I contact {row['name']}. In under 120 words: who decides, what they "
            "care about, every objection raised, every promise or callback date (and whether it is due), what we "
            "already tried and how it went, and the single best next step.",
            tags=[f"lead:{lead_id}"],
        )
        return {"lead": row, "brief": r.text, "memories": [_mem_dict(m, f"M{i}") for i, m in enumerate(r.memories, 1)]}

    async def draft(self, lead_id: str, use_memory: bool = True, goal: str | None = None) -> dict[str, Any]:
        row = self.crm.get(lead_id)
        now = self.clock()
        goal = goal or "Move this lead to the next step (usually a site survey)."
        system = DRAFT_SYSTEM.format(company=self.company, city=self.city)
        parts = [f"Today: {now:%A %d %B %Y, %H:%M} IST", f"Goal: {goal}", "LEAD (CRM row):", lead_card(row)]

        lead_mem: list[Memory] = []
        playbook_mem: list[Memory] = []
        playbook_text: str | None = None
        if use_memory:
            segment = SEGMENT_LABELS[row["segment"]].lower()
            lead_mem, playbook_mem, pb = await asyncio.gather(
                self.memory.recall(
                    f"Everything about {row['name']}: family and decision makers, language, objections, promises, "
                    "callback dates, what we sent and how they reacted",
                    tags=[f"lead:{lead_id}"], max_tokens=1500, now=now),
                self.memory.recall(
                    f"Which follow-up approaches worked or failed with {segment} leads and leads with similar "
                    f"objections to {row['name']}? {row.get('last_message') or ''}",
                    tags=["kind:outcome"], max_tokens=2000, now=now),
                self.memory.playbook(),
            )
            lead_ids = {m.id for m in lead_mem}
            playbook_mem = [m for m in playbook_mem if m.id not in lead_ids][:10]
            playbook_text = pb.get("content")
            parts += ["WHAT WE KNOW ABOUT THIS LEAD (from memory):", _fmt(lead_mem, "M") or "(nothing yet)",
                      "WHAT HAPPENED WITH SIMILAR LEADS (from memory):", _fmt(playbook_mem, "P") or "(nothing yet)"]
            if playbook_text:
                parts += ["TEAM PLAYBOOK (learned by the memory system from all past outcomes):", playbook_text]
        elif row.get("last_message"):
            # A stateless bot still sees the message it is replying to. That is all it sees.
            parts += ["LATEST MESSAGE FROM LEAD:", row["last_message"]]

        out = await self.llm.json(system, "\n\n".join(parts))
        return {
            "lead": row,
            "use_memory": use_memory,
            "draft": {k: out.get(k) for k in ("message", "language", "approach", "send_at", "reasoning", "avoid")},
            "memories": [_mem_dict(m, f"M{i}") for i, m in enumerate(lead_mem, 1)]
                        + [_mem_dict(m, f"P{i}") for i, m in enumerate(playbook_mem, 1)],
            "playbook_used": bool(playbook_text),
        }

    async def due(self) -> dict[str, Any]:
        now = self.clock()
        r = await self.memory.reflect(
            f"Today is {now:%A %d %B %Y}. List every OPEN lead (not converted, not lost) with a promised callback, "
            "meeting or follow-up that is due today, overdue, or due in the next 7 days. Use the exact date promised. "
            "Remember that missing a promised callback has cost us deals before.",
            response_schema=DUE_SCHEMA,
        )
        items = (r.structured or {}).get("due") if r.structured else None
        return {"items": items or [], "text": r.text if not items else None,
                "memories": [_mem_dict(m, f"M{i}") for i, m in enumerate(r.memories, 1)]}

    async def ask(self, question: str) -> dict[str, Any]:
        r = await self.memory.reflect(f"Today is {self.clock():%d %B %Y}. {question}")
        return {"answer": r.text, "memories": [_mem_dict(m, f"M{i}") for i, m in enumerate(r.memories, 1)]}

    # ------------------------------------------------------------------ history replay

    def _event_time(self, e: Event) -> datetime:
        base = datetime.combine(self.clock().date(), time(11, 0), tzinfo=IST)
        return base + timedelta(days=e.day)

    def _event_item(self, e: Event) -> dict[str, Any]:
        row = self.crm.get(e.lead_id)
        seg = SEGMENT_LABELS[row["segment"]]
        if e.kind == "outcome":
            content = (f"Follow-up outcome for {row['name']} ({seg}, {row['locality']}). "
                       f"Approach tried: {e.approach.replace('_', ' ')}. Result: {e.result}. {e.text}")
            tags = self._tags(row, "outcome", [f"approach:{e.approach}", f"result:{e.result}"])
            ctx = "result of a sales follow-up approach"
        else:
            content = f"{e.channel.title()} with {row['name']} ({seg}, {row['locality']}): {e.text}"
            tags = self._tags(row, "interaction", [f"channel:{e.channel}"])
            ctx = f"sales conversation with a solar lead via {e.channel}"
        when = self._event_time(e)
        return {"content": content, "tags": tags, "timestamp": when, "context": ctx,
                "document_id": f"{e.lead_id}-{e.kind}-{when:%Y%m%d}-{zlib.crc32(e.text.encode()) % 100_000}",
                "metadata": {"lead_id": e.lead_id, "kind": e.kind}}

    async def replay(self, until_day: int = 0, since_day: int | None = None) -> dict[str, Any]:
        events = [e for e in events_until(until_day) if since_day is None or e.day > since_day]
        await self.memory.retain_many([self._event_item(e) for e in events])
        for e in events:
            when = self._event_time(e).isoformat()
            if e.kind == "interaction":
                self.crm.touch(e.lead_id, message=e.text, when=when)
            else:
                self.crm.touch(e.lead_id, when=when,
                               status={"converted": "won", "lost": "lost"}.get(e.result or ""))
        self._spawn(self.memory.refresh_playbook())
        return {"retained": len(events), "until_day": until_day}
