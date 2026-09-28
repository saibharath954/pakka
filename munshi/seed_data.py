"""Eight weeks of WhatsApp orders for Sri Venkateswara Agencies, a (fictional)
FMCG distributor in Secunderabad, Hyderabad, serving ten kirana stores.

Every retailer has habits that only experience teaches: private nicknames for
products ("blue wala", "red paste", "RL250"), units that mean different things
("box" = case), repeat orders ("same as last time", "usual list"), and a
language mix (Hinglish, Telugu-English, Urdu-Hindi). The same nickname can mean
different products to different shops: "blue wala" is Surf Excel to Sharma
Kirana and Lay's Magic Masala to Sai Ram Kirana.

The generator is deterministic (fixed seed) and every message carries its gold
lines, so the learning curve can be measured, not asserted.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .catalog import BY_CODE

WEEKS = 8
TODAY_OFFSET = WEEKS * 7  # history covers days -56 .. -1; day 0 is "today"


@dataclass(frozen=True)
class Item:
    sku: str
    phrases: tuple[str, ...]  # how THIS retailer writes it; first entries are the private nickname(s)
    qty: tuple[int, ...]
    unit: str  # "case" or "pcs"


@dataclass(frozen=True)
class Retailer:
    id: str
    name: str
    area: str
    owner: str
    style: str
    order_weekdays: tuple[int, ...]  # 0 = Monday
    case_word: str
    pcs_word: str
    items: tuple[Item, ...]
    greeting: tuple[str, ...]
    closing: tuple[str, ...]
    repeat_phrase: str | None = None  # e.g. "same as last time"


@dataclass
class GoldLine:
    sku: str
    units: int
    phrase: str | None = None  # how the retailer wrote it (None for lines implied by "same as last time")


@dataclass
class Message:
    id: str
    retailer_id: str
    day: int  # offset from today
    hour: int
    text: str
    gold: list[GoldLine] = field(default_factory=list)
    week: int = 0


It = Item
RETAILERS: list[Retailer] = [
    Retailer("R01", "Sharma Kirana", "Ameerpet", "Rajesh Sharma", "Hinglish", (0, 3), "cartoon", "pcs",
             (It("SURF-EW-1K", ("blue wala", "blue wala surf"), (1, 2), "case"),
              It("PARLEG-5", ("parle 5 wala", "chota parle"), (1, 2), "case"),
              It("MAGGI-70", ("maggi",), (1,), "case"),
              It("TATASALT-1K", ("tata salt",), (1,), "case"),
              It("FREEDOM-1L", ("tel", "tel packet"), (1, 2), "case"),
              It("REDLABEL-250", ("red label 250",), (12, 24), "pcs")),
             ("Bhai order likho", "Namaste bhai", "Bhaiya order"), ("jaldi bhejna", "shaam tak chahiye", ""),
             repeat_phrase="same as last time"),
    Retailer("R02", "Lakshmi General Stores", "Kukatpally", "K. Srinivas", "Telugu-English", (1,), "box", "pieces",
             (It("CLOSEUP-150", ("red paste",), (1,), "case"),
              It("FREEDOM-1L", ("oil packet", "oil packets"), (1, 2), "case"),
              It("3ROSES-100", ("3 roses chinna",), (1,), "case"),
              It("3ROSES-250", ("3 roses pedda",), (12, 24), "pcs"),
              It("SANTOOR-125", ("sabbu", "sabbulu"), (1,), "case"),
              It("VIM-BAR-300", ("vim bar",), (1,), "case")),
             ("Anna order", "Namaskaram anna", "Anna ee order pampandi"), ("repu morning ki kavali", "thanks anna", "")),
    Retailer("R03", "Balaji Super Market", "Dilsukhnagar", "Balaji Rao", "short codes", (2,), "cs", "pcs",
             (It("REDLABEL-250", ("RL250",), (1, 2), "case"),
              It("SURF-QW-1K", ("SEQ1",), (1,), "case"),
              It("COLGATE-200", ("CG200",), (1,), "case"),
              It("GOLDDROP-1L", ("GD1L",), (2, 3), "case"),
              It("HORLICKS-500", ("HRL500",), (12,), "pcs"),
              It("DARKFANTASY-75", ("DF75",), (1,), "case")),
             ("Balaji SM PO:", "PO Balaji Super Mkt -"), ("pls confirm rates", "")),
    Retailer("R04", "Hussaini Traders", "Tolichowki", "Syed Hussaini", "Urdu-Hindi", (5,), "dabba", "nag",
             (It("TAJ-250", ("chai patti", "chai patti taj"), (12, 24), "pcs"),
              It("LIFEBUOY-125", ("lal sabun",), (1,), "case"),
              It("PARLEG-5", ("5 rupay wala biscuit",), (1, 2), "case"),
              It("AASHIRVAAD-5K", ("atta 5 kilo",), (1, 2), "case"),
              It("BOURBON-150", ("bourbon",), (1,), "case")),
             ("Assalamualaikum bhai", "Bhai maal bhejo"), ("Allah hafiz", "jumme ke pehle", "")),
    Retailer("R05", "Venkat Provisions", "Secunderabad", "Venkat Reddy", "voice-note transcript", (0, 4), "box", "packets",
             (It("BOOST-500", ("boost",), (6, 12), "pcs"),
              It("TATASALT-1K", ("salt",), (1,), "case"),
              It("GOLDDROP-1L", ("gold drop",), (1,), "case"),
              It("YIPPEE-70", ("yippee",), (1,), "case"),
              It("RIN-1K", ("rin",), (1,), "case")),
             ("[voice note] haa sir venkat provisions nunchi", "[voice note] sir venkat here"),
             ("ok sir thank you", "ade sir"), repeat_phrase="usual list"),
    Retailer("R06", "Sai Ram Kirana", "LB Nagar", "Sai Kumar", "Hinglish", (4,), "box", "packet",
             (It("LAYS-MM-52", ("blue wala", "blue lays"), (1, 2), "case"),
              It("LAYS-CO-52", ("green wala", "green lays"), (1,), "case"),
              It("KURKURE-MC-90", ("kurkure",), (1,), "case"),
              It("PARLEG-250", ("parle bada",), (1,), "case"),
              It("MAGGI-70", ("maggi",), (1,), "case")),
             ("Bhai", "Anna order"), ("fast bhejo", "")),
    Retailer("R07", "New Hyderabad Stores", "Mehdipatnam", "Abdul Rahman", "Hinglish", (5,), "peti", "pc",
             (It("DETTOL-125", ("green sabun", "green soap"), (1,), "case"),
              It("HARPIC-500", ("bathroom wala",), (6, 12), "pcs"),
              It("LIZOL-500", ("floor wala",), (6,), "pcs"),
              It("DETTOL-HW-200", ("handwash",), (12,), "pcs"),
              It("VIM-LIQ-500", ("vim liquid",), (6, 12), "pcs")),
             ("Bhai maal likho", "Salaam bhai"), ("", "kal subah")),
    Retailer("R08", "Reddy Mart", "Kompally", "Narsimha Reddy", "Telugu-English", (0,), "box", "nos",
             (It("AASHIRVAAD-10K", ("atta 10",), (2, 3), "case"),
              It("GOLDDROP-15L", ("oil dabba", "tin"), (2, 4), "pcs"),
              It("TATASALT-1K", ("tata salt",), (2,), "case"),
              It("SURF-EW-1K", ("surf excel easy wash",), (1,), "case"),
              It("PARACHUTE-500", ("parachute 500",), (12,), "pcs")),
             ("Reddy Mart order:", "Anna Reddy Mart"), ("Monday delivery", "")),
    Retailer("R09", "Anand Stores", "Miyapur", "Anand Kumar", "English, dozens", (3,), "case", "dozen",
             (It("GOODDAY-CASHEW", ("good day",), (2, 4), "dozen"),
              It("MARIE-GOLD", ("marie",), (2,), "dozen"),
              It("BRU-50", ("bru",), (1, 2), "dozen"),
              It("CLINIC-175", ("clinic plus",), (1,), "dozen"),
              It("COLGATE-200", ("colgate 200",), (2,), "dozen")),
             ("Hi, order from Anand Stores:", "Anand Stores order"), ("Thanks", "")),
    Retailer("R10", "Fathima Kirana", "Mallepally", "Fathima Begum", "Hindi", (2,), "peti", "packet",
             (It("MAGGI-12PK", ("maggi bada",), (1,), "case"),
              It("SURF-QW-1K", ("surf",), (1,), "case"),
              It("PARACHUTE-250", ("chota parachute",), (12,), "pcs"),
              It("CINTHOL-100", ("cinthol",), (1,), "case"),
              It("WHEEL-1K", ("wheel",), (1,), "case")),
             ("Bhai", "Bhaiya"), ("udhaar agle hafte", "")),
]

BY_ID = {r.id: r for r in RETAILERS}


def _units(item: Item, qty: int) -> int:
    if item.unit == "case":
        return qty * BY_CODE[item.sku].case_qty
    if item.unit == "dozen":
        return qty * 12
    return qty


def _render_line(r: Retailer, item: Item, qty: int, rng: random.Random) -> tuple[str, str]:
    phrase = rng.choice(item.phrases)
    unit = r.case_word if item.unit == "case" else (r.pcs_word if item.unit == "pcs" else "dozen")
    if r.style == "short codes":
        return f"{phrase} - {qty}{unit}", phrase
    if rng.random() < 0.5:
        return f"{phrase} {qty} {unit}", phrase
    return f"{qty} {unit} {phrase}", phrase


def _merge(lines: list[GoldLine]) -> list[GoldLine]:
    """What actually got delivered: same SKU on two lines is one line."""
    out: dict[str, int] = {}
    for g in lines:
        out[g.sku] = out.get(g.sku, 0) + g.units
    return [GoldLine(k, v) for k, v in out.items()]


def generate(seed: int = 7) -> list[Message]:
    rng = random.Random(seed)
    messages: list[Message] = []
    last_gold: dict[str, list[GoldLine]] = {}
    n = 0
    for day in range(-TODAY_OFFSET, 0):
        weekday = (day + TODAY_OFFSET) % 7  # day -56 is a Monday by construction
        for r in RETAILERS:
            if weekday not in r.order_weekdays:
                continue
            n += 1
            week = (day + TODAY_OFFSET) // 7 + 1
            repeat = bool(r.repeat_phrase and r.id in last_gold and rng.random() < (0.6 if r.id == "R05" else 0.35))
            if repeat:
                in_last = {g.sku for g in last_gold[r.id]}
                fresh = [it for it in r.items if it.sku not in in_last]
                extra_item = rng.choice(fresh or list(r.items))
                extra_qty = rng.choice(extra_item.qty)
                extra_text, extra_phrase = _render_line(r, extra_item, extra_qty, rng)
                gold = [GoldLine(g.sku, g.units) for g in last_gold[r.id]]
                gold.append(GoldLine(extra_item.sku, _units(extra_item, extra_qty), extra_phrase))
                body = f"{r.repeat_phrase}, plus {extra_text} extra"
            else:
                picks = rng.sample(r.items, k=min(len(r.items), rng.randint(3, 5)))
                lines, gold = [], []
                for it in picks:
                    q = rng.choice(it.qty)
                    text_line, phrase = _render_line(r, it, q, rng)
                    lines.append(text_line)
                    gold.append(GoldLine(it.sku, _units(it, q), phrase))
                sep = "\n" if r.style in ("short codes", "English, dozens") or rng.random() < 0.6 else ", "
                body = sep.join(lines)
            closing = rng.choice(r.closing)
            text = f"{rng.choice(r.greeting)}\n{body}" + (f"\n{closing}" if closing else "")
            messages.append(Message(f"M{n:03d}", r.id, day, rng.choice((8, 9, 10, 11, 17, 18, 19)), text, gold, week))
            last_gold[r.id] = _merge(gold)
    return messages


# Messages that arrive "today" during the live demo. Not part of the replayed history.
LIVE_MESSAGES: list[tuple[str, str]] = [
    ("R01", "Bhai order likho\nblue wala 2 cartoon\ntel 1 cartoon\nchota parle 1 cartoon\nshaam tak chahiye"),
    ("R06", "Anna order\nblue wala 2 box, green wala 1 box, kurkure 1 box"),
    ("R02", "Namaskaram anna\nred paste 1 box\noil packets 2 box\nsabbu 1 box\nrepu morning ki kavali"),
    ("R05", "[voice note] haa sir venkat provisions nunchi, usual list pampandi, plus boost 6 packets extra, ok sir thank you"),
    ("R03", "Balaji SM PO:\nRL250 - 2cs\nGD1L - 3cs\nDF75 - 1cs\npls confirm rates"),
]
