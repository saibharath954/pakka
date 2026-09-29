# Video script (~3 min) + titles

**Setup before recording:** run `python scripts/replay.py` (live Hindsight), then `uvicorn munshi.app:app`. Browser at 110–125% zoom, 1080p, notifications off. Optional: the Hindsight Cloud UI open in a second tab on the bank.

## 1. Intro (0:00–0:30): face cam, then the inbox
> "Hi, I'm Sai Bharath. I build WhatsApp automation for Indian small businesses. Distributors here get most of their orders as WhatsApp messages like this one, full of shop-specific slang. One veteran clerk knows what every shop means. I built Munshi, an order desk that learns that knowledge, using Hindsight as its memory."

**Show:** the inbox with five new orders.

## 2. The problem (0:30–1:00): memory off
**Show:** click **Sai Ram Kirana**, then flip **Memory → Off**.
> "Here's 'blue wala 2 box, green wala 1 box'. Without memory, this is what any LLM gives you: unknown, unknown, a guess. It can split the message fine. It just has no idea what this shop means by blue wala."

## 3. Live demo (1:00–2:30)
**a) Memory on (1:00–1:25).** Flip **Memory → On**.
> "Memory on. Blue wala is Lay's Magic Masala: see the evidence dots, confirmed five times for this shop. Green wala has only been seen once, so Munshi pre-fills it but asks me. It never auto-accepts something it's only seen once."

**b) Same words, different shop (1:25–1:50).** Click **Sharma Kirana**.
> "Now Sharma Kirana also says blue wala, and here it's Surf Excel. Every memory is tagged per shop and recalled with strict tags, so they never leak into each other." Press **Ctrl+Enter**. "Confirm, and here's exactly what got retained to Hindsight, plus the Tally voucher."

**c) Usual list (1:50–2:05).** Click **Venkat Provisions**.
> "A voice note: 'usual list pampandi, plus boost extra'. Munshi recalls his last order from the past 35 days and rebuilds it."

**d) Teach it live (2:05–2:20).** **+ New** → Sai Ram Kirana → "green wala 1 box" → confirm. Send it again.
> "Second confirmation. Now it auto-accepts. That's the learning loop."

**e) The curve (2:20–2:30).** **Learning curve** tab, hover week 4.
> "And this is eight weeks replayed: 31% to 98% auto-accepted, with zero wrong auto-accepts. Without memory it's stuck around 20%, and it's wrong nine times."

## 4. Takeaway (2:30–3:00): face cam
> "What surprised me: memory didn't make the agent bolder, it made it more careful. Counting real confirmations before trusting a memory is why it got faster without ever posting a wrong order. The code and the replay harness are linked below."

---

## YouTube title options
1. "Blue Wala" Means Two Different Things. My AI Order Desk Learned Both.
2. Memory Off vs Memory On: Same WhatsApp Order, Very Different Agent
3. I Measured My AI Agent Learning: 31% → 98% in 8 Weeks
4. Building an AI Order Clerk for Indian Distributors (Hindsight Memory)
5. My Agent Never Guesses an Order, and Still Got 3x Faster

## Description
Munshi: a WhatsApp order desk that learns every shop's language, built on Hindsight agent memory.
Code: https://github.com/saibharath954/Munshi
Article: [ARTICLE LINK]
Hindsight: https://github.com/vectorize-io/hindsight
Docs: https://hindsight.vectorize.io/
