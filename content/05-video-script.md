# Video script: ~3 minutes (Prompt 5)

Record at 1080p. Browser zoom 125%, terminal font 18pt+, notifications off.
Before recording: `python scripts/seed.py --reset --until -40` (weeks 1–2 only), `uvicorn pakka.app:app`, and open the Hindsight Cloud UI in a second tab on the `sunkiran-solar` bank.

## 1. Intro (0:00–0:30): face cam + UI
**Show:** you on camera, then the Pakka UI.
> "Hi, I'm Sai Bharath. I build WhatsApp automation for Indian small businesses, and they all have the same problem: the sales history lives in chat threads nobody remembers. So I built Pakka, a follow-up agent that uses Hindsight as its memory. It remembers every lead, and it learns which follow-ups actually close."

## 2. The problem (0:30–1:00): memory OFF
**Show:** click **Suresh Varma** → *Draft: without vs with memory*. Point at the left pane only.
> "Suresh lives in an apartment and asked for a 3kW price on IndiaMART. Here's a normal LLM with just his message: price and a discount, send now. Sounds fine. But we've already lost a lead exactly this way. The model just doesn't know that."

## 3. Live demo (1:00–2:30)
**a) Learning curve (1:00–1:30).** Show the Playbook panel: thin.
> "Right now memory only has two weeks of history, so the playbook barely knows anything."

Choose *History → Load the remaining weeks*. Cut ahead in the edit while it retains. Switch to the Hindsight UI tab and show memories arriving with tags `lead:*`, `kind:outcome`. Back in Pakka, click **Refresh** on the playbook.
> "Every chat and every outcome is retained with tags. Hindsight consolidates them into observations, and this mental model, the sales playbook, gets rewritten automatically. I never wrote these rules. Apartments need RWA approval first. Commercial buyers want payback, not subsidy. Never miss a callback."

**b) The before/after (1:30–2:00).** Suresh again → compare. Now read the right pane.
> "Same lead, now with memory. No price before the survey, because Neha ghosted after an early quote. It attaches the RWA NOC template and offers to present at his society meeting, because that got Priya's society to approve in three weeks. And every reason cites a memory. Expand this and you see the exact memories it recalled."

**c) Personal memory (2:00–2:15).** Click **Padma Reddy** → compare.
> "Padma garu was referred by Lakshmi Devi. With memory the message is in Telugu and loops in her daughter. That's exactly what worked for Lakshmi."

**d) Promises (2:15–2:30).** Click *Due now → Check memory*.
> "And this is one reflect call with a JSON schema: who did we promise to call? Irfan tonight after six. Rahul the Monday after his society vote. We lost Kiran Kumar because nobody called when we said we would."

## 4. Takeaway (2:30–3:00): face cam
> "What surprised me: the memory didn't matter until I retained outcomes, not just conversations. 'We tried X and they ignored it' is what turns a search box into something that learns. And one Hindsight bank with strict tags gave me per-lead privacy and cross-lead learning at the same time. Code's in the description. Thanks for watching."

---

## 5 YouTube title options
1. My Sales Agent Stopped Sending Discounts After I Gave It Memory
2. Stateless vs Memory: Same Lead, Two Very Different AI Follow-ups
3. I Built an AI That Learns Which WhatsApp Follow-ups Close Deals
4. This Agent Rewrote Its Own Sales Playbook (Hindsight Memory Demo)
5. AI Sales Follow-ups That Remember Every Lead: Built With Hindsight

## Description template
Pakka: a WhatsApp sales follow-up agent with Hindsight agent memory.
Code: [REPO LINK]
Article: [ARTICLE LINK]
Hindsight: https://github.com/vectorize-io/hindsight
Docs: https://hindsight.vectorize.io/
