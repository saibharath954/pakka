# Reddit link post

Subreddit: **r/LLMDevs** (best technical fit). Alternatives: r/AIAgents, r/AIMemory, r/SideProject.
Type: **Link post** → the article URL.

**Title:** "Blue wala" means Surf to one shop, chips to another: measuring an agent that learns customer slang

**First comment (context, not promo):**

Built an order-desk agent for Indian FMCG distributors who take orders over WhatsApp. The interesting bits, if you're adding memory to an agent:

- One Hindsight bank + strict tag matching per customer (`any_strict` / `all_strict`), so the same nickname can mean different SKUs for different shops.
- The LLM only parses the message. A nickname auto-accepts only after 2 independent confirmations, counted from the raw retained chunks (`include_chunks=True`), not from paraphrased facts.
- "Same as last time" uses recall with a `temporal_window`.
- A replay harness scores 96 messages against gold labels, with memory on and off: 31% → 98% of lines auto-accepted, 0 wrong auto-accepts vs 9 without memory (bundled offline run; the script reproduces it against live Hindsight).

Repo: https://github.com/saibharath954/Munshi. Happy to answer questions about the gate or the eval.
