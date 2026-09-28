# I gave my sales agent Hindsight memory. It stopped discounting.

The first draft my follow-up agent wrote for an apartment owner in Hyderabad was *"Hi Suresh, we have a special discount this week, 3kW starts at ₹1.9 lakh, shall I send the quotation?"* It's a perfectly reasonable message. It's also exactly the message that had already lost us a deal three weeks earlier.

The model wasn't the problem. It had no way of knowing that. This post is about what changed when I gave it a memory, specifically [Hindsight, an open-source agent memory system](https://github.com/vectorize-io/hindsight), and about which design decisions mattered more than I expected.

## The problem: sales knowledge lives in WhatsApp threads

In India, small businesses sell over WhatsApp. Take a rooftop-solar installer in Hyderabad. Leads come from IndiaMART, JustDial, and Instagram ads. Three reps work maybe 150 open leads, and the real CRM is a pile of chat threads.

Everything important is in those threads:

- Srinivas in Miyapur won't commit because his neighbour waited five months for the PM Surya Ghar subsidy.
- Lakshmi Devi garu reads Telugu, not long English messages, and her son in Bangalore makes the money decisions.
- Rahul in Gachibowli can't install anything until his residents' welfare association (RWA) approves use of the terrace.
- Kiran in LB Nagar said "call me after two weeks, my daughter's wedding is on". Nobody did, and he signed with a competitor.

None of this fits in a CRM field. And none of it reaches an LLM that's asked to "write a follow-up for Suresh Varma".

So I built **Pakka**. It retains every conversation and every follow-up outcome, and before it drafts anything it recalls what it knows. The part I care most about: it learns *which approaches work for which kind of lead*, without me writing those rules.

## How it hangs together

![Architecture](../docs/architecture.png)

The stack is deliberately boring: FastAPI, a static HTML page, [Hindsight](https://hindsight.vectorize.io/) for memory, and Groq's `gpt-oss-120b` for drafting. There is one memory bank per company. The CRM row (name, phone, segment, status) sits in a JSON file, because that's spreadsheet data. Anything *learned* goes into Hindsight.

The agent has four jobs:

1. **Retain** each conversation and each outcome ("sent the subsidy proof → replied").
2. **Brief** a rep before a call, using `reflect` over that lead's memories only.
3. **Draft** the next follow-up from this lead's history, what happened with similar leads, and the team playbook.
4. **Surface promises** that are due, like "call after 6pm today" or "the Monday after the RWA vote".

## The core decision: one bank, many tags

My first instinct was a bank per lead. That's clean isolation, but it's useless for the question that matters most: *what worked on other apartment leads?* Cross-lead learning is the whole point.

So there's one bank, and every memory is tagged at retain time:

```python
def _tags(self, row, kind, extra=None):
    return [f"lead:{row['id']}", f"segment:{row['segment']}", f"kind:{kind}", *(extra or [])]

async def log_outcome(self, lead_id, approach, result, text, when=None, refresh=True):
    row = self.crm.get(lead_id)
    content = (f"Follow-up outcome for {row['name']} ({SEGMENT_LABELS[row['segment']]}, {row['locality']}). "
               f"Approach tried: {approach.replace('_', ' ')}. Result: {result}. {text}")
    tags = self._tags(row, "outcome", [f"approach:{approach}", f"result:{result}"])
    await self.memory.retain(content, tags=tags, when=when or self.clock(), ...)
```

When drafting, the agent runs two recalls in parallel with different tag scopes. One is strictly this lead. The other is outcomes across all leads, ranked by how similar the situation is:

```python
lead_mem, playbook_mem, pb = await asyncio.gather(
    self.memory.recall(
        f"Everything about {row['name']}: family and decision makers, language, objections, promises, ...",
        tags=[f"lead:{lead_id}"], max_tokens=1500, now=now),
    self.memory.recall(
        f"Which follow-up approaches worked or failed with {segment} leads and leads with similar "
        f"objections to {row['name']}? {row.get('last_message') or ''}",
        tags=["kind:outcome"], max_tokens=2000, now=now),
    self.memory.playbook(),
)
```

One detail worth knowing before you start: Hindsight's default tag matching (`any`) *includes untagged memories*. That's sensible for a general bank, but wrong when "everything about Suresh" must never contain facts about Rahul. The fix is `tags_match="any_strict"`. If you scope memory by tags, read that part of the docs twice.

Hindsight's recall runs semantic, keyword (BM25), graph and temporal retrieval in parallel, and reranks the merged results. So the second query finds Neha's and Rahul's outcomes for Suresh without me hand-writing a "similar leads" function. I didn't have to build a retrieval pipeline. I just had to retain the right things with the right tags.

## The playbook nobody writes

Recall gives you facts. What I actually wanted was the thing a senior sales manager carries around in their head: *discounts don't move independent-house owners who are scared about the subsidy; proof of recent subsidy credits does.*

Hindsight has two features that fit this almost exactly. **Observations** are consolidated, evidence-backed beliefs built from many raw facts. When new evidence arrives, an observation gets refined rather than overwritten. **Mental models** are standing questions whose answers Hindsight keeps rewriting in the background. Pakka creates one at startup:

```python
await self.client.acreate_mental_model(
    self.bank_id,
    id=PLAYBOOK_ID,
    name="Sales playbook: what actually closes",
    source_query=PLAYBOOK_QUERY,  # "which approaches got replies or conversions ... by segment and objection"
    max_tokens=1200,
    trigger={"refresh_after_consolidation": True},
)
```

That's the entire learning loop. Log an outcome, Hindsight consolidates it into observations, and the playbook gets rewritten. Reading the playbook afterwards is a database read, not an LLM call, so it costs nothing to include in every draft.

To show this, the demo replays eight weeks of sales history (40 events across 13 leads) in two stages. After the first two weeks the playbook is thin: a couple of ignored discounts and one reply to a subsidy explanation. After all eight weeks it has segment-level rules. Apartments need the RWA NOC template before any price. Commercial buyers get a payback calculation, not the residential subsidy brochure. Salaried couples reply after 7pm. Never miss a promised callback date. None of those rules appear anywhere in my code or prompts. I seeded plain conversations and results, and Hindsight found the patterns.

## Before and after, same lead

Suresh Varma lives in an apartment in Nallagandla. His IndiaMART message: *"What is price for 3kW? Is subsidy there for flats? Please send quotation fast, comparing 3 vendors."*

**Without memory** (the model sees the CRM row and his message, like any WhatsApp bot would): it quotes a price and offers a discount, to be sent now.

**With Hindsight memory**, the draft:

- does **not** quote a per-watt price, citing that Neha Kapoor ghosted after an early quote and was lost on price;
- attaches the RWA NOC template and offers to present at his society meeting, citing that Priya Nair's society approved in three weeks after exactly that;
- mentions the group-housing subsidy for common areas, which came up in Rahul Mehta's RWA presentation.

Every claim in the reasoning cites a memory id like `[P3]`, and the UI shows the underlying memory. When a rep asks "why is it not just sending the price?", the answer is on screen with dates.

Two other moments made memory feel real rather than decorative:

- **Padma Reddy** was referred by Lakshmi Devi. Her draft comes out in Telugu, suggests looping in her daughter, and leads with subsidy proof. That combination worked for Lakshmi Devi. Her CRM row has no language field. The preference comes from memory.
- **Due now** is a single `reflect` call with a JSON schema. It lists Mohammed Irfan ("call back today after 6pm") and Rahul Mehta ("the Monday after the committee vote"). The vote date was *updated* in a later message, and reflect used the newer date.

## Decisions that mattered more than I expected

**No function calling.** The obvious design gives the agent `recall` and `retain` as tools and lets it decide when to use them. With open-weight models on a fast provider, tool calling is the least reliable part of the stack: malformed calls, skipped recalls, retries. So I used plain Python orchestration instead. The code decides what to recall, and the model gets one prompt and returns one JSON object:

```python
for attempt in range(3):
    kwargs = {"model": self.model, "messages": messages, "temperature": 0.4}
    if attempt == 0:
        kwargs["response_format"] = {"type": "json_object"}
    try:
        resp = await self.client.chat.completions.create(**kwargs)
        return extract_json(resp.choices[0].message.content or "")
    except Exception as err:
        ...
```

The memory decisions don't need to be agentic. They need to be correct every time.

**A fair baseline.** A "no memory" agent that sees nothing at all is a strawman. Pakka's baseline sees the lead's last message, which is exactly what a real WhatsApp bot has. The comparison is only interesting if the only difference is the memory.

**Relative dates in seed data.** Hard-coded dates in the history would make the "due today" callback two weeks overdue a week later. Every event is an offset from today, so temporal recall behaves the same whenever you run it.

## Lessons if you're adding memory to an agent

1. **Retain outcomes, not just conversations.** Conversations tell the agent about a customer. Outcomes ("approach X → ignored") are what let it learn. If you only retain chat logs, you have a very expensive search box.
2. **Scope with tags, and use the strict variants.** One bank plus tags gets you per-entity isolation *and* cross-entity learning. `any_strict` stops untagged memories from leaking into scoped queries.
3. **Let the memory system hold the rules.** A mental model that refreshes after consolidation replaced the playbook I would otherwise have written into a prompt, and that prompt would have been wrong by next month.
4. **Make memory visible.** Citing memory ids in drafts builds trust with the people using the tool, and it's the fastest way to debug bad recalls.
5. **Keep orchestration boring.** Deterministic retain/recall around a JSON-only LLM call beat an agent loop on reliability, latency and cost.

If you want to understand the model behind this, Vectorize's explainer on [what agent memory is](https://vectorize.io/what-is-agent-memory) is a good start. The [Hindsight docs](https://hindsight.vectorize.io/) cover retain, recall, reflect and mental models in detail. Pakka's code is on GitHub: **[link to your repo]**.

The discount message never got sent. The RWA template did.
