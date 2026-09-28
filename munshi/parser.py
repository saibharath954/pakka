"""Turning a WhatsApp message into order lines, and turning memories into evidence.

Two parsers produce the same shape, a list of `RawLine(phrase, qty, unit)`:

* `rule_parse` is deterministic. It is the offline parser and the fallback when
  the LLM misbehaves.
* `llm_parse` (in agent.py) asks the LLM for the same JSON and is better on messy
  voice-note transcripts.

Neither parser decides which SKU a phrase means. That decision is made by
`resolve()` from evidence: confirmations recalled from memory, or an
unambiguous catalogue match.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from .catalog import BY_CODE, CODE_RE, catalog_match
from .memory import Memory

CASE_WORDS = {"cartoon", "cartoons", "carton", "cartons", "ctn", "case", "cases", "cs", "box", "boxes", "peti",
              "dabba", "dabbe"}
DOZEN_WORDS = {"dozen", "doz", "dz"}
PCS_WORDS = {"pcs", "pc", "piece", "pieces", "packet", "packets", "pkt", "nos", "no", "nag", "units"}
UNIT_WORDS = CASE_WORDS | DOZEN_WORDS | PCS_WORDS
REPEAT_RE = re.compile(r"\b(same as last( time)?|usual( list| order)?|regular (list|order)|last order|wahi order|same order)\b",
                       re.I)
NOISE = {"extra", "plus", "and", "aur", "also", "more", "send", "bhejo", "kavali", "pampandi", "chahiye", "pls"}

AUTO_MIN_CONFIRMATIONS = 2  # a nickname auto-resolves only after this many independent confirmations


@dataclass
class RawLine:
    phrase: str
    qty: int
    unit: str  # case | dozen | pcs


@dataclass
class Evidence:
    sku: str
    confirmations: int
    memory_ids: list[str] = field(default_factory=list)
    dates: list[str] = field(default_factory=list)


def norm(phrase: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", phrase.lower()))


def unit_of(word: str | None) -> str:
    w = (word or "").lower()
    if w in CASE_WORDS:
        return "case"
    if w in DOZEN_WORDS:
        return "dozen"
    return "pcs"


def to_units(sku: str, qty: int, unit: str) -> int:
    if unit == "case":
        return qty * BY_CODE[sku].case_qty
    if unit == "dozen":
        return qty * 12
    return qty


def is_repeat(text: str) -> bool:
    return bool(REPEAT_RE.search(text))


_QTY_UNIT = re.compile(r"(?<![a-z0-9])(\d+)\s*(" + "|".join(sorted(UNIT_WORDS, key=len, reverse=True)) + r")\b", re.I)
_BARE_NUM = re.compile(r"(?<![a-z0-9])(\d+)(?![a-z0-9])", re.I)


def _segments(text: str) -> list[str]:
    text = re.sub(r"^\[voice note\]\s*", "", text.strip(), flags=re.I)
    parts = re.split(r"[\n,;]+|\s+(?:aur|and)\s+", text, flags=re.I)
    return [p.strip(" -:.") for p in parts if p and p.strip(" -:.")]


def rule_parse(text: str) -> list[RawLine]:
    lines: list[RawLine] = []
    for seg in _segments(text):
        if REPEAT_RE.fullmatch(seg.strip().lower()) or not re.search(r"\d", seg):
            continue
        m = list(_QTY_UNIT.finditer(seg))
        if m:
            hit = m[-1]
            qty, unit = int(hit.group(1)), unit_of(hit.group(2))
            rest = seg[:hit.start()] + " " + seg[hit.end():]
        else:
            nums = list(_BARE_NUM.finditer(seg))
            if not nums:
                continue
            hit = nums[-1]
            qty, unit = int(hit.group(1)), "pcs"
            rest = seg[:hit.start()] + " " + seg[hit.end():]
        words = norm(rest).split()
        while words and words[0] in NOISE:  # "plus 12 packets boost extra"
            words.pop(0)
        while words and words[-1] in NOISE - {"plus"}:
            words.pop()
        phrase = " ".join(words)
        if phrase and qty > 0:
            lines.append(RawLine(phrase, qty, unit))
    return lines


# ----------------------------------------------------------------------------- evidence from memory

_CONFIRM_RE = re.compile(r'wrote\s+["“](?P<phrase>[^"”]+)["”].{0,80}?meant\s+(?P<code>' + CODE_RE.pattern[3:-3] + r")",
                         re.S)
_ORDER_RE = re.compile(r"Confirmed order (?P<oid>\S+) from .+? on (?P<date>\d{4}-\d{2}-\d{2})[^:]*:(?P<lines>[^\n]*)")
_ORDER_LINE_RE = re.compile(r"(?P<code>" + CODE_RE.pattern[3:-3] + r")\s*x\s*(?P<units>\d+)")


def alias_evidence(memories: list[Memory]) -> dict[str, dict[str, Evidence]]:
    """phrase -> sku -> Evidence, counting each retained confirmation document once."""
    seen: set[str] = set()
    out: dict[str, dict[str, Evidence]] = defaultdict(dict)
    for m in memories:
        key = m.document_id or m.raw
        if key in seen:
            continue
        for match in _CONFIRM_RE.finditer(m.raw):
            seen.add(key)
            ph, code = norm(match.group("phrase")), match.group("code")
            ev = out[ph].setdefault(code, Evidence(code, 0))
            ev.confirmations += 1
            ev.memory_ids.append(m.id)
            if m.when:
                ev.dates.append(m.when[:10])
    return out


def lookup(phrase: str, evidence: dict[str, dict[str, Evidence]]) -> list[Evidence]:
    """Evidence for a phrase, best first. Exact phrase match only: 'blue wala' is not 'blue lays'."""
    cands = evidence.get(norm(phrase), {})
    return sorted(cands.values(), key=lambda e: e.confirmations, reverse=True)


def last_order(memories: list[Memory]) -> tuple[str | None, str | None, dict[str, int], str | None]:
    """Most recent confirmed order in the recalled memories: (order_id, date, {sku: units}, memory_id)."""
    best = (None, None, {}, None)
    for m in memories:
        for om in _ORDER_RE.finditer(m.raw):
            if best[1] is None or om.group("date") > best[1]:
                lines = {lm.group("code"): int(lm.group("units")) for lm in _ORDER_LINE_RE.finditer(om.group("lines"))}
                best = (om.group("oid"), om.group("date"), lines, m.id)
    return best


# ----------------------------------------------------------------------------- resolution

@dataclass
class Line:
    phrase: str
    qty: int
    unit: str
    sku: str | None
    units: int
    status: str  # auto | review | unknown
    basis: str  # memory | catalog | repeat | memory-once | conflict | guess | none
    confirmations: int = 0
    memory_ids: list[str] = field(default_factory=list)
    note: str = ""
    alternatives: list[str] = field(default_factory=list)


def resolve(raw: RawLine, evidence: dict[str, dict[str, Evidence]] | None, llm_guess: str | None = None) -> Line:
    """Decide the SKU for one line, and whether it is safe to auto-accept."""
    cands = lookup(raw.phrase, evidence) if evidence is not None else []
    if cands:
        best = cands[0]
        rival = cands[1] if len(cands) > 1 else None
        if rival and rival.confirmations >= best.confirmations:
            return Line(raw.phrase, raw.qty, raw.unit, best.sku, to_units(best.sku, raw.qty, raw.unit), "review",
                        "conflict", best.confirmations, best.memory_ids,
                        f"memory disagrees: {best.sku} ×{best.confirmations} vs {rival.sku} ×{rival.confirmations}",
                        [c.sku for c in cands])
        status = "auto" if best.confirmations >= AUTO_MIN_CONFIRMATIONS else "review"
        basis = "memory" if status == "auto" else "memory-once"
        note = (f"learned: confirmed {best.confirmations}× for this retailer" if status == "auto"
                else "seen once before; one more confirmation and it auto-accepts")
        return Line(raw.phrase, raw.qty, raw.unit, best.sku, to_units(best.sku, raw.qty, raw.unit), status, basis,
                    best.confirmations, best.memory_ids, note, [c.sku for c in cands])

    sku, how = catalog_match(raw.phrase)
    if sku and how == "exact":
        return Line(raw.phrase, raw.qty, raw.unit, sku.code, to_units(sku.code, raw.qty, raw.unit), "auto", "catalog",
                    note="matches the item master")
    guess = llm_guess if llm_guess in BY_CODE else (sku.code if sku else None)
    if guess:
        return Line(raw.phrase, raw.qty, raw.unit, guess, to_units(guess, raw.qty, raw.unit), "review", "guess",
                    note="best guess from the catalogue; needs the operator")
    return Line(raw.phrase, raw.qty, raw.unit, None, 0, "unknown", "none", note="no idea what this is yet")
