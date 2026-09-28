from munshi.catalog import catalog_match
from munshi.memory import Memory
from munshi.parser import alias_evidence, is_repeat, last_order, resolve, rule_parse, RawLine
from munshi.seed_data import generate
from munshi.parser import norm


def test_rule_parser_recovers_every_phrase_in_the_history():
    for m in generate():
        gold = sorted(norm(g.phrase) for g in m.gold if g.phrase)
        assert sorted(x.phrase for x in rule_parse(m.text)) == gold, m.text


def test_quantities_units_and_numbers_inside_names():
    lines = rule_parse("3 roses chinna 1 box\natta 10 2 box\nRL250 - 2cs\nclinic plus 1 dozen, plus boost 6 packets extra")
    assert [(x.phrase, x.qty, x.unit) for x in lines] == [
        ("3 roses chinna", 1, "case"), ("atta 10", 2, "case"), ("rl250", 2, "case"),
        ("clinic plus", 1, "dozen"), ("boost", 6, "pcs")]


def test_repeat_detection():
    assert is_repeat("same as last time, plus tel 1 cartoon extra")
    assert is_repeat("haa sir usual list pampandi")
    assert not is_repeat("blue wala 2 cartoon")


def _conf(i, rid, phrase, sku, date="2026-09-01"):
    text = f'Order-desk confirmation: Shop ({rid}) wrote "{phrase}" and it meant {sku} (x). Date {date}.'
    return Memory(f"m{i}", text, "world", date, [f"retailer:{rid}"], f"doc{i}", text)


def test_nickname_needs_two_confirmations_before_auto_accept():
    once = alias_evidence([_conf(1, "R01", "blue wala", "SURF-EW-1K")])
    line = resolve(RawLine("blue wala", 2, "case"), once)
    assert (line.sku, line.status, line.units) == ("SURF-EW-1K", "review", 24)
    twice = alias_evidence([_conf(1, "R01", "blue wala", "SURF-EW-1K"), _conf(2, "R01", "blue wala", "SURF-EW-1K")])
    assert resolve(RawLine("blue wala", 2, "case"), twice).status == "auto"


def test_same_fact_recalled_twice_counts_once():
    m = _conf(1, "R01", "blue wala", "SURF-EW-1K")
    dup = Memory("m1b", "extracted fact", "world", None, [], "doc1", m.chunk)
    assert alias_evidence([m, dup])["blue wala"]["SURF-EW-1K"].confirmations == 1


def test_conflicting_memories_go_to_the_operator():
    ev = alias_evidence([_conf(1, "R01", "surf", "SURF-EW-1K"), _conf(2, "R01", "surf", "SURF-QW-1K")])
    line = resolve(RawLine("surf", 1, "case"), ev)
    assert line.status == "review" and line.basis == "conflict"


def test_without_memory_nicknames_are_unknown_but_catalog_names_resolve():
    assert resolve(RawLine("blue wala", 1, "case"), None).status == "unknown"
    salt = resolve(RawLine("tata salt", 1, "case"), None)
    assert (salt.sku, salt.status, salt.units) == ("TATASALT-1K", "auto", 25)
    sku, how = catalog_match("maggi")
    assert how == "ambiguous"  # 70g single or 12-pack: the catalogue alone cannot tell


def test_last_order_picks_the_most_recent():
    def mk(i, d, body):
        return Memory(f"o{i}", "x", "world", d, [], f"o{i}", f"Confirmed order SO-{i} from Shop (R05) on {d} (Monday): {body}")

    oid, date, lines, _ = last_order([mk(1, "2026-09-01", "RIN-1K x 12"), mk(2, "2026-09-15", "RIN-1K x 24; BOOST-500 x 6")])
    assert (oid, date, lines) == ("SO-2", "2026-09-15", {"RIN-1K": 24, "BOOST-500": 6})
