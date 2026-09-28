"""The distributor's item master: what Tally calls stock items.

Prices are dealer prices per unit in rupees, rounded, for demo purposes. Case
sizes follow common trade packs. `keywords` are the generic words a catalogue
search would match on; they deliberately do NOT include any retailer's private
nicknames ("blue wala", "red paste"). Those have to be learned.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SKU:
    code: str
    name: str
    case_qty: int
    price: float
    keywords: tuple[str, ...]

    @property
    def case_price(self) -> float:
        return self.price * self.case_qty


def _s(code, name, case_qty, price, *kw):
    return SKU(code, name, case_qty, price, tuple(kw))


CATALOG: list[SKU] = [
    # Detergents
    _s("SURF-EW-1K", "Surf Excel Easy Wash 1kg", 12, 128, "surf", "excel", "easy", "wash", "1kg"),
    _s("SURF-QW-1K", "Surf Excel Quick Wash 1kg", 12, 196, "surf", "excel", "quick", "wash", "1kg"),
    _s("RIN-1K", "Rin Detergent Powder 1kg", 12, 94, "rin", "powder", "1kg"),
    _s("WHEEL-1K", "Wheel Active 2in1 1kg", 12, 62, "wheel", "active", "1kg"),
    _s("TIDE-1K", "Tide Plus Jasmine & Rose 1kg", 12, 112, "tide", "plus", "1kg"),
    _s("ARIEL-1K", "Ariel Matic Top Load 1kg", 12, 238, "ariel", "matic", "1kg"),
    _s("VIM-BAR-300", "Vim Dishwash Bar 300g", 36, 28, "vim", "bar", "300g"),
    _s("VIM-LIQ-500", "Vim Dishwash Liquid 500ml", 24, 108, "vim", "liquid", "gel", "500ml"),
    # Personal care
    _s("LIFEBUOY-125", "Lifebuoy Total 10 Soap 125g", 72, 34, "lifebuoy", "soap", "125g"),
    _s("LUX-150", "Lux Soft Touch Soap 150g", 72, 42, "lux", "soap", "150g"),
    _s("SANTOOR-125", "Santoor Sandal & Turmeric Soap 125g", 72, 38, "santoor", "soap", "125g"),
    _s("DETTOL-125", "Dettol Original Soap 125g", 72, 52, "dettol", "soap", "original", "125g"),
    _s("CINTHOL-100", "Cinthol Lime Soap 100g", 72, 36, "cinthol", "lime", "soap", "100g"),
    _s("COLGATE-200", "Colgate Strong Teeth 200g", 48, 104, "colgate", "strong", "teeth", "paste", "200g"),
    _s("CLOSEUP-150", "Close-Up Red Hot Gel 150g", 48, 96, "closeup", "close", "up", "gel", "paste", "150g"),
    _s("PEPSODENT-150", "Pepsodent Germicheck 150g", 48, 88, "pepsodent", "paste", "150g"),
    _s("CLINIC-175", "Clinic Plus Shampoo 175ml", 48, 118, "clinic", "plus", "shampoo", "175ml"),
    _s("PARACHUTE-250", "Parachute Coconut Oil 250ml", 48, 102, "parachute", "coconut", "oil", "250ml"),
    _s("PARACHUTE-500", "Parachute Coconut Oil 500ml", 24, 196, "parachute", "coconut", "oil", "500ml"),
    _s("DETTOL-HW-200", "Dettol Handwash Original 200ml refill", 48, 62, "dettol", "handwash", "refill"),
    # Home care
    _s("HARPIC-500", "Harpic Power Plus 500ml", 24, 94, "harpic", "toilet", "cleaner", "500ml"),
    _s("LIZOL-500", "Lizol Floor Cleaner Citrus 500ml", 24, 104, "lizol", "floor", "cleaner", "500ml"),
    # Staples
    _s("TATASALT-1K", "Tata Salt 1kg", 25, 26, "tata", "salt", "1kg"),
    _s("AASHIRVAAD-5K", "Aashirvaad Shudh Chakki Atta 5kg", 4, 238, "aashirvaad", "atta", "5kg"),
    _s("AASHIRVAAD-10K", "Aashirvaad Shudh Chakki Atta 10kg", 2, 462, "aashirvaad", "atta", "10kg"),
    _s("FREEDOM-1L", "Freedom Refined Sunflower Oil 1L pouch", 10, 142, "freedom", "sunflower", "oil", "1l", "pouch"),
    _s("FORTUNE-1L", "Fortune Sunlite Refined Sunflower Oil 1L pouch", 10, 148, "fortune", "sunlite", "sunflower", "oil", "1l"),
    _s("GOLDDROP-1L", "Gold Drop Refined Sunflower Oil 1L pouch", 10, 144, "gold", "drop", "sunflower", "oil", "1l"),
    _s("GOLDDROP-15L", "Gold Drop Refined Sunflower Oil 15L tin", 1, 2040, "gold", "drop", "oil", "15l", "tin"),
    # Beverages
    _s("REDLABEL-250", "Brooke Bond Red Label Tea 250g", 48, 128, "red", "label", "brooke", "bond", "tea", "250g"),
    _s("3ROSES-100", "Brooke Bond 3 Roses Tea 100g", 96, 48, "3", "roses", "three", "tea", "100g"),
    _s("3ROSES-250", "Brooke Bond 3 Roses Tea 250g", 48, 118, "3", "roses", "three", "tea", "250g"),
    _s("TAJ-250", "Taj Mahal Tea 250g", 48, 176, "taj", "mahal", "tea", "250g"),
    _s("BRU-50", "Bru Instant Coffee 50g", 96, 108, "bru", "coffee", "instant", "50g"),
    _s("BOOST-500", "Boost Health Drink 500g jar", 24, 248, "boost", "500g"),
    _s("HORLICKS-500", "Horlicks Classic Malt 500g jar", 24, 256, "horlicks", "500g"),
    # Biscuits & snacks
    _s("PARLEG-5", "Parle-G Original Glucose ₹5 pack", 144, 4.5, "parle", "g", "glucose", "5"),
    _s("PARLEG-250", "Parle-G Original Glucose 250g family pack", 48, 26, "parle", "g", "glucose", "250g", "family"),
    _s("GOODDAY-CASHEW", "Britannia Good Day Cashew 200g", 48, 36, "good", "day", "cashew", "britannia"),
    _s("MARIE-GOLD", "Britannia Marie Gold 250g", 48, 38, "marie", "gold", "britannia"),
    _s("BOURBON-150", "Britannia Bourbon 150g", 60, 32, "bourbon", "britannia"),
    _s("DARKFANTASY-75", "Sunfeast Dark Fantasy Choco Fills 75g", 60, 36, "dark", "fantasy", "sunfeast"),
    _s("MAGGI-70", "Maggi 2-Minute Masala Noodles 70g", 96, 13, "maggi", "noodles", "masala", "70g"),
    _s("MAGGI-12PK", "Maggi 2-Minute Masala Noodles 12-pack 840g", 8, 158, "maggi", "noodles", "12", "pack", "family"),
    _s("YIPPEE-70", "Sunfeast YiPPee! Magic Masala 70g", 96, 13, "yippee", "noodles", "70g"),
    _s("LAYS-MM-52", "Lay's India's Magic Masala 52g", 40, 18, "lays", "magic", "masala", "chips", "52g"),
    _s("LAYS-CO-52", "Lay's American Style Cream & Onion 52g", 40, 18, "lays", "cream", "onion", "chips", "52g"),
    _s("KURKURE-MC-90", "Kurkure Masala Munch 90g", 40, 18, "kurkure", "masala", "munch", "90g"),
]

BY_CODE = {s.code: s for s in CATALOG}
CODE_RE = re.compile(r"\b(" + "|".join(re.escape(c) for c in sorted(BY_CODE, key=len, reverse=True)) + r")\b")

STOPWORDS = {"and", "aur", "plus", "extra", "also", "send", "pls", "please", "bhai", "sir", "anna", "garu",
             "ji", "the", "of", "wala", "wali", "ka", "ki", "ke", "de", "do", "dena", "pampandi", "kavali"}


def tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower().replace("close-up", "closeup")) if t not in STOPWORDS]


def catalog_match(phrase: str) -> tuple[SKU | None, str]:
    """Match a phrase against the catalogue by generic keywords only.

    Returns (sku, basis) where basis is "exact" when one SKU clearly wins,
    "ambiguous" when several tie, or "none".
    """
    words = set(tokens(phrase))
    if not words:
        return None, "none"
    scored = []
    for sku in CATALOG:
        kw = set(sku.keywords)
        hits = len(words & kw)
        if hits:
            # Reward covering the SKU's distinguishing words, penalise unmatched phrase words.
            scored.append((hits / len(kw) + hits * 0.25 - 0.05 * len(words - kw), sku))
    if not scored:
        return None, "none"
    scored.sort(key=lambda x: x[0], reverse=True)
    best = scored[0]
    brand_hit = bool(words & {best[1].keywords[0]})
    if len(scored) > 1 and scored[1][0] >= best[0] - 0.08:
        return best[1], "ambiguous"
    if not brand_hit or best[0] < 0.55:
        return best[1], "ambiguous"
    return best[1], "exact"


def catalog_prompt() -> str:
    return "\n".join(f"{s.code} | {s.name} | case of {s.case_qty}" for s in CATALOG)
