"""Eight weeks of sales history for SunKiran Solar, a (fictional) rooftop-solar
installer in Hyderabad.

Every event is dated relative to "today" so the demo always looks current:
day -54 is eight weeks ago, day 0 is today. The history is written so that real
patterns are hidden in it, the same way they hide in a real sales team's
WhatsApp threads:

* apartment leads stall on RWA (residents' welfare association) approval, and a
  ready-made NOC template + offer to present at the society meeting unsticks them;
* independent-house owners fear the PM Surya Ghar subsidy "never comes", and
  proof of recent subsidy credits works where discounts don't;
* commercial buyers get no residential subsidy, so a payback calculation wins;
* quoting a price per watt before the site survey makes leads ghost;
* older owners reply to Telugu voice notes and want their son/daughter looped in;
* salaried couples reply after 7pm, not at 11am;
* a promised callback date that is missed loses the deal.

Nothing here is labelled as a "lesson". Hindsight has to find the patterns.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Lead:
    id: str
    name: str
    segment: str  # independent_house | apartment | commercial | farm
    locality: str
    source: str
    phone: str
    language: str = "English"
    monthly_bill_inr: int | None = None
    status: str = "open"  # open | won | lost (set by replaying outcomes)


@dataclass(frozen=True)
class Event:
    day: int  # offset from today, negative = past
    lead_id: str
    kind: str  # interaction | outcome
    text: str
    channel: str = "whatsapp"
    approach: str | None = None  # outcome events: the follow-up angle that was tried
    result: str | None = None  # outcome events: replied | ignored | converted | lost | stalled
    tags: tuple[str, ...] = field(default_factory=tuple)


LEADS: list[Lead] = [
    Lead("L01", "Srinivas Rao", "independent_house", "Miyapur", "JustDial", "+91 98480 1xxxx", monthly_bill_inr=4200),
    Lead("L02", "Lakshmi Devi", "independent_house", "Dilsukhnagar", "Referral", "+91 94401 2xxxx", language="Telugu", monthly_bill_inr=3100),
    Lead("L03", "Rahul Mehta", "apartment", "Gachibowli (Lakeview Heights)", "Facebook ad", "+91 99890 3xxxx", monthly_bill_inr=5600),
    Lead("L04", "Neha Kapoor", "apartment", "Kondapur", "IndiaMART", "+91 90000 4xxxx", monthly_bill_inr=4800),
    Lead("L05", "Dr. Farhan Siddiqui", "commercial", "Tolichowki (clinic)", "Google Maps", "+91 98663 5xxxx", monthly_bill_inr=38000),
    Lead("L06", "Venkat Reddy", "independent_house", "Kompally", "JustDial", "+91 97013 6xxxx", monthly_bill_inr=6800),
    Lead("L07", "Kiran Kumar", "independent_house", "LB Nagar", "Walk-in", "+91 91000 7xxxx", monthly_bill_inr=3900),
    Lead("L08", "Sameer Khan", "commercial", "Mehdipatnam (garments shop)", "IndiaMART", "+91 98490 8xxxx", monthly_bill_inr=14500),
    Lead("L09", "Priya Nair", "apartment", "Manikonda (Green Meadows)", "Facebook ad", "+91 95500 9xxxx", monthly_bill_inr=4100),
    Lead("L10", "Anjali & Rohit Sharma", "independent_house", "Kukatpally", "Instagram", "+91 99080 0xxxx", monthly_bill_inr=5200),
    Lead("L11", "Mohammed Irfan", "independent_house", "Attapur", "JustDial", "+91 93910 1xxxx", monthly_bill_inr=4600),
    # Fresh leads for the live demo: no outcomes yet.
    Lead("L12", "Suresh Varma", "apartment", "Nallagandla (Aparna-style gated society)", "IndiaMART", "+91 98855 2xxxx", monthly_bill_inr=5000),
    Lead("L13", "Padma Reddy", "independent_house", "Alwal", "Referral", "+91 94900 3xxxx", language="Telugu", monthly_bill_inr=3600),
]


def _i(day: int, lead: str, text: str, channel: str = "whatsapp") -> Event:
    return Event(day, lead, "interaction", text, channel=channel)


def _o(day: int, lead: str, approach: str, result: str, text: str) -> Event:
    return Event(day, lead, "outcome", text, approach=approach, result=result)


EVENTS: list[Event] = [
    # ---- L01 Srinivas Rao: subsidy fear, discount fails, subsidy proof wins ----
    _i(-54, "L01", "Srinivas Rao (Miyapur, G+1 independent house, bill ~Rs 4,200/month) asked for a 3kW quote. "
       "Said: 'My neighbour put solar last year, subsidy came after 5 months only, full tension. I don't want that headache.'"),
    _o(-52, "L01", "discount", "ignored",
       "Sent Srinivas Rao a 5% festive discount offer on 3kW. Two blue ticks, no reply for 6 days."),
    _o(-46, "L01", "subsidy_proof", "replied",
       "Sent Srinivas Rao a note that we file the PM Surya Ghar application and DISCOM net-metering paperwork ourselves, "
       "plus a screenshot (shared with customer consent) of a Kukatpally customer's Rs 78,000 subsidy credited 34 days after commissioning. "
       "He replied within an hour: 'This is what I wanted to know. Come on Saturday for site visit.'"),
    _o(-33, "L01", "subsidy_proof", "converted",
       "Srinivas Rao signed for 3kW on-grid after site survey. Advance Rs 25,000 paid by UPI. Said the subsidy tracking promise was the deciding factor."),

    # ---- L02 Lakshmi Devi: English text ignored, Telugu voice note + son works ----
    _i(-53, "L02", "Lakshmi Devi garu (62, Dilsukhnagar, independent house) was referred by Srinivas Rao's wife. Prefers Telugu. "
       "Her son Harsha works in Bangalore and handles money decisions."),
    _o(-52, "L02", "english_long_text", "ignored",
       "Sent Lakshmi Devi a long English WhatsApp message with system specs and price breakup. No reply in 5 days."),
    _o(-47, "L02", "telugu_voice_note_plus_family", "replied",
       "Sent Lakshmi Devi a 40-second Telugu voice note explaining subsidy and savings simply, and asked if we can call Harsha on Saturday. "
       "She replied with a voice note: 'Saturday 11 ki Harsha tho matladandi.' (talk to Harsha at 11)."),
    _o(-40, "L02", "telugu_voice_note_plus_family", "converted",
       "Call with son Harsha on Saturday, he approved 2kW for Lakshmi Devi's house. Converted. Harsha asked us to always keep him on the group."),

    # ---- L03 Rahul Mehta: apartment, quote stalls, RWA template works ----
    _i(-50, "L03", "Rahul Mehta (Gachibowli, Lakeview Heights, 14th floor flat) wants solar for his flat. Terrace is common property. "
       "Asked 'what is the price for 3kW?'"),
    _o(-49, "L03", "price_quote_first", "stalled",
       "Sent Rahul Mehta Rs 1.95 lakh quote for 3kW before any site visit. He said 'let me check with the association' and went silent for 2 weeks."),
    _o(-34, "L03", "rwa_noc_template_plus_society_presentation", "replied",
       "Sent Rahul Mehta a ready RWA NOC template and offered to present to Lakeview Heights managing committee on a Sunday. "
       "He forwarded it to the RWA secretary Mr. Chandrasekhar the same day. RWA asked for a 20-minute presentation."),
    _i(-20, "L03", "Presented at Lakeview Heights RWA meeting. Committee interested in a 40kW common-area system (lifts, pumps, corridor lights) "
       "under the group housing subsidy, plus individual flat allocations. Secretary Chandrasekhar wants a written proposal. "
       "Rahul Mehta said 'call me on the 5th of next month once the committee votes'."),
    _i(-3, "L03", "Rahul Mehta messaged: committee vote moved to this coming Sunday. He asked us to follow up the Monday after the vote.", channel="whatsapp"),

    # ---- L04 Neha Kapoor: price per watt before survey, ghosted ----
    _i(-48, "L04", "Neha Kapoor (Kondapur apartment) asked on IndiaMART for per-watt price for 3kW."),
    _o(-48, "L04", "price_quote_first", "ignored",
       "Sent Neha Kapoor Rs 62/watt price over WhatsApp before any site survey. She read it and never replied. "
       "Followed up twice. No response."),
    _o(-30, "L04", "price_quote_first", "lost",
       "Marked Neha Kapoor lost. Found out from her neighbour she went with a cheaper installer quoting Rs 55/watt. "
       "We competed on price per watt and lost on price per watt."),

    # ---- L05 Dr. Farhan Siddiqui: commercial, wrong subsidy brochure, payback calc wins ----
    _i(-47, "L05", "Dr. Farhan Siddiqui runs a clinic in Tolichowki. Electricity bill about Rs 38,000/month, heavy AC load. Asked about subsidy."),
    _o(-46, "L05", "residential_subsidy_brochure", "ignored",
       "Sent Dr. Farhan the PM Surya Ghar residential subsidy brochure. He replied annoyed: 'This is for homes, I asked about my clinic. Please read my message.'"),
    _o(-44, "L05", "payback_calculation", "replied",
       "Sent Dr. Farhan a one-page payback calculation for 15kW: no residential subsidy for commercial, but payback about 3.5 years on "
       "his tariff, and he should ask his CA about accelerated depreciation. He replied 'Now we are talking' and booked a visit."),
    _o(-36, "L05", "payback_calculation", "converted",
       "Dr. Farhan Siddiqui signed 15kW for the clinic. Referred his brother's pharmacy."),

    # ---- L06 Venkat Reddy: EMI objection, EMI-vs-bill comparison wins ----
    _i(-45, "L06", "Venkat Reddy (Kompally, bill Rs 6,800) likes the idea but said 'cannot pay 3 lakhs at once, is EMI there?'"),
    _o(-44, "L06", "emi_vs_bill_comparison", "replied",
       "Sent Venkat Reddy a comparison: bank solar loan EMI about Rs 2,900/month vs his expected bill saving of about Rs 5,500/month. "
       "He replied 'So I save money from month one? Send the bank details.'"),
    _o(-31, "L06", "emi_vs_bill_comparison", "converted",
       "Venkat Reddy converted, 5kW with bank solar loan."),

    # ---- L07 Kiran Kumar: callback date missed, lost to competitor ----
    _i(-42, "L07", "Kiran Kumar (LB Nagar) is interested in 3kW but said: 'Daughter's wedding is on, call me after 2 weeks, not before.'"),
    _o(-14, "L07", "missed_callback_date", "lost",
       "Called Kiran Kumar 4 weeks later instead of 2. He had already signed with BrightRoof Solar. "
       "He said: 'You said you will call, nobody called.' Lost a warm lead because the promised callback date was missed."),

    # ---- L08 Sameer Khan: commercial shop, discount ignored, payback replied ----
    _i(-38, "L08", "Sameer Khan (garments shop, Mehdipatnam, bill Rs 14,500) enquired on IndiaMART about 5kW for the shop."),
    _o(-37, "L08", "discount", "ignored",
       "Sent Sameer Khan a 7% discount offer for the shop. No reply."),
    _o(-29, "L08", "payback_calculation", "replied",
       "Sent Sameer Khan a payback calculation (about 3.8 years on commercial tariff). He replied asking to compare 5kW vs 7kW. "
       "Negotiation ongoing; he wants a final quote after Dasara stock clearance."),

    # ---- L09 Priya Nair: apartment, RWA template sent first, converted ----
    _i(-36, "L09", "Priya Nair (Manikonda, Green Meadows apartments) asked about solar for her flat. Terrace is shared."),
    _o(-35, "L09", "rwa_noc_template_plus_society_presentation", "replied",
       "Before quoting any price, sent Priya Nair the RWA NOC template and offered to present to Green Meadows committee. "
       "She shared it in the residents' WhatsApp group; 6 other flat owners asked questions."),
    _o(-15, "L09", "rwa_noc_template_plus_society_presentation", "converted",
       "Green Meadows RWA approved terrace use in 3 weeks. Priya Nair signed 2kW. Two neighbours from the same society asked for site visits."),

    # ---- L10 Sharma couple: messages at 11am ignored, 8pm replies ----
    _i(-28, "L10", "Anjali & Rohit Sharma (Kukatpally, both work in HITEC City IT companies) enquired via Instagram about 3kW."),
    _o(-27, "L10", "daytime_message_11am", "ignored",
       "Sent the Sharmas a follow-up at 11:05am on a weekday. Not read until night, no reply."),
    _o(-25, "L10", "evening_message_after_7pm", "replied",
       "Sent the Sharmas a follow-up at 8:10pm. Anjali replied in 4 minutes and booked a Sunday site visit."),
    _o(-12, "L10", "evening_message_after_7pm", "converted",
       "Anjali & Rohit Sharma signed 3kW. Rohit said evenings and Sundays are the only time they can talk."),

    # ---- L11 Mohammed Irfan: subsidy fear, proof works, callback due today ----
    _i(-10, "L11", "Mohammed Irfan (Attapur) asked: 'Is subsidy really coming? My cousin in Tolichowki is still waiting 4 months.'"),
    _o(-9, "L11", "subsidy_proof", "replied",
       "Sent Mohammed Irfan our subsidy tracking process and anonymised proof of 3 recent subsidy credits (all within 45 days). "
       "He replied positively: 'OK, this gives confidence.'"),
    _i(-6, "L11", "Mohammed Irfan asked us to call him back today after 6pm to fix the site survey date; he is travelling until then.",
       channel="call"),

    # ---- L12 Suresh Varma: fresh apartment lead (live demo) ----
    _i(-1, "L12", "Suresh Varma (Nallagandla gated society, apartment) enquired on IndiaMART: "
       "'What is price for 3kW? Is subsidy there for flats? Please send quotation fast, comparing 3 vendors.'"),

    # ---- L13 Padma Reddy: fresh Telugu-speaking lead (live demo) ----
    _i(-2, "L13", "Padma Reddy garu (Alwal, independent house, around 65) was referred by Lakshmi Devi. Speaks Telugu. "
       "Her daughter Swathi in Pune pays the bills. Worried: 'subsidy vastunda ledha? (will subsidy come or not?)'"),
]


def events_until(day: int) -> list[Event]:
    """All events on or before a given day offset (used to replay history in stages)."""
    return [e for e in EVENTS if e.day <= day]
