# Reddit link post

Subreddit: r/LLMDevs (best fit for a technical memory write-up). Alternatives: r/AIAgents, r/AIMemory, r/SideProject.
Type: **Link post** → article URL.

**Title:**
I gave my WhatsApp sales agent Hindsight memory. It stopped discounting.

**Optional first comment (context, not promo):**
Built this for how Indian SMBs actually sell (IndiaMART leads, WhatsApp threads, RWA approvals, the PM Surya Ghar subsidy). A few things that might be useful if you're adding memory to an agent:
- one Hindsight bank + tags per lead, with `tags_match="any_strict"` so untagged memories don't leak into lead-scoped recall
- retain *outcomes* ("approach → replied/ignored"), not just chats, or the agent never learns what works
- a mental model with `refresh_after_consolidation` is the "playbook", so there are no hand-written rules in the prompt
- no function calling: plain-Python orchestration + a JSON-only LLM call was far more reliable on open models

Code: [REPO LINK]. Happy to answer questions about the tag scoping or the baseline comparison.
