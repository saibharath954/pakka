"""Replay eight weeks of orders and measure whether Munshi actually learns.

For each historical message, in time order:

1. Munshi processes it with whatever memory holds *at that moment*;
2. its lines are scored against the gold order;
3. the simulated operator confirms the correct order, exactly as they would in
   the UI, and that confirmation is retained.

Run once with memory and once without (the "without" run never retains). The
difference between the two curves is what memory is worth.

Metrics are per gold line (SKU after merging):
  auto_correct  auto-accepted with the right SKU and quantity
  auto_wrong    auto-accepted but wrong: the number that must stay at zero
  touched       the operator had to look at it
A message is "touchless" when every line was auto_correct and nothing wrong was auto-accepted.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any, Callable

from .agent import IST, Munshi
from .parser import norm
from .seed_data import Message, generate


def message_time(m: Message, today: datetime) -> datetime:
    base = datetime.combine(today.date(), time(0, 0), tzinfo=IST)
    return base + timedelta(days=m.day, hours=m.hour, minutes=(int(m.id[1:]) * 7) % 60)


def score(parsed: dict, m: Message) -> dict[str, int]:
    gold: dict[str, int] = defaultdict(int)
    for g in m.gold:
        gold[g.sku] += g.units
    pred: dict[str, int] = defaultdict(int)
    pred_auto: dict[str, bool] = {}
    for ln in parsed["lines"]:
        if not ln["sku"]:
            continue
        pred[ln["sku"]] += ln["units"]
        pred_auto[ln["sku"]] = pred_auto.get(ln["sku"], True) and ln["status"] == "auto"
    auto_correct = auto_wrong = touched = 0
    for sku, units in gold.items():
        if pred_auto.get(sku) and pred.get(sku) == units:
            auto_correct += 1
        elif pred_auto.get(sku):
            auto_wrong += 1
        else:
            touched += 1
    auto_wrong += sum(1 for sku, a in pred_auto.items() if a and sku not in gold)
    return {"lines": len(gold), "auto_correct": auto_correct, "auto_wrong": auto_wrong, "touched": touched,
            "touchless": int(auto_correct == len(gold) and auto_wrong == 0)}


def operator_final(parsed: dict, m: Message) -> list[dict]:
    """What the operator ends up confirming: the gold order, keeping Munshi's suggestion so corrections are recorded."""
    by_phrase = {norm(ln["phrase"]): ln for ln in parsed["lines"] if ln["basis"] != "repeat"}
    final = []
    for g in m.gold:
        if g.phrase is None:
            final.append({"phrase": None, "sku": g.sku, "units": g.units, "basis": "repeat"})
            continue
        ln = by_phrase.get(norm(g.phrase), {})
        final.append({"phrase": g.phrase, "sku": g.sku, "units": g.units,
                      "basis": ln.get("basis", "none"), "suggested": ln.get("sku")})
    return final


async def replay(agent: Munshi, today: datetime, use_memory: bool,
                 on_progress: Callable[[int, int], None] | None = None) -> dict[str, Any]:
    messages = generate()
    weekly: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    samples: list[dict] = []
    for i, m in enumerate(messages, 1):
        when = message_time(m, today)
        parsed = await agent.process(m.retailer_id, m.text, when=when, use_memory=use_memory)
        s = score(parsed, m)
        w = weekly[m.week]
        for k, v in s.items():
            w[k] += v
        w["messages"] += 1
        if use_memory:
            items, _ = agent.confirm_items(m.retailer_id, operator_final(parsed, m), when,
                                           f"SO-{when:%y%m%d}-{m.id}")
            await agent.memory.retain_many(items)
        if m.retailer_id in ("R01", "R06") and len(samples) < 40:
            samples.append({"id": m.id, "week": m.week, "retailer": m.retailer_id, "text": m.text,
                            "auto": parsed["stats"]["auto"], "review": parsed["stats"]["review"]})
        if on_progress:
            on_progress(i, len(messages))
    weeks = []
    for wk in sorted(weekly):
        w = weekly[wk]
        weeks.append({"week": wk, **w,
                      "auto_rate": round(w["auto_correct"] / w["lines"], 4) if w["lines"] else 0,
                      "touchless_rate": round(w["touchless"] / w["messages"], 4) if w["messages"] else 0})
    return {"weeks": weeks, "samples": samples}


async def learning_curve(agent: Munshi, today: datetime, mode: str, out: Path | None = None,
                         on_progress: Callable[[str, int, int], None] | None = None) -> dict[str, Any]:
    await agent.memory.reset()
    without = await replay(agent, today, use_memory=False,
                           on_progress=(lambda i, n: on_progress("without", i, n)) if on_progress else None)
    with_mem = await replay(agent, today, use_memory=True,
                            on_progress=(lambda i, n: on_progress("with", i, n)) if on_progress else None)
    result = {
        "generated_at": datetime.now(IST).isoformat(timespec="seconds"),
        "mode": mode,
        "parser": "llm" if agent.llm else "rules",
        "gate": "nickname auto-accepts after 2 confirmations",
        "with_memory": with_mem["weeks"],
        "without_memory": without["weeks"],
        "totals": {k: _totals(v["weeks"]) for k, v in (("with_memory", with_mem), ("without_memory", without))},
    }
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2))
    return result


def _totals(weeks: list[dict]) -> dict[str, int]:
    keys = ("lines", "auto_correct", "auto_wrong", "touched", "touchless", "messages")
    return {k: sum(w[k] for w in weeks) for k in keys}
