# Submission plan: deadline 29 Sep

The submission form needs: repo link, LinkedIn post, article link, video link, Reddit link, feedback. Every team member also fills the profile form: https://forms.gle/AXWnanWsEEir6xSP9 (the team won't be reviewed without it).

## Tonight (in order; about 5–6 hours total)

| # | Task | Time | Done when |
|---|---|---|---|
| 1 | Create a **public** GitHub repo (e.g. `pakka`) and push only the `pakka/` folder to it. **Do not** make the Research repo public: it has your salary and strategy notes | 10 min | Repo URL opens logged-out |
| 2 | Sign up for Hindsight Cloud, apply promo code in Billing, create an API key. Get a Groq key | 15 min | Both keys in `.env` |
| 3 | `pip install -r requirements.txt && python scripts/smoke.py` | 5 min | 4/4 lines print |
| 4 | `python scripts/seed.py --reset`, run the app, and try the 5 demo steps in the README | 30 min | See "verify before recording" below |
| 5 | Take 3 screenshots from the live run: compare panes on Suresh, the playbook panel, Due now. Save as `docs/ui.png` etc. and restore the image line in the README | 15 min | README shows the UI |
| 6 | Record the team video (script: `05-video-script.md`) and upload to YouTube as **Public**, with the thumbnail | 60–90 min | Public URL |
| 7 | Edit the article in your own voice, add screenshots + `docs/architecture.png`, and publish on Dev.to, Hashnode or Medium | 45 min | Public URL |
| 8 | Post on LinkedIn (`03-linkedin-post.md`): article link as the first comment, Hindsight link as the second | 10 min | Post URL |
| 9 | Reddit link post (`04-reddit-post.md`) | 5 min | Post URL |
| 10 | **Each teammate**: their own article (a different angle, pick another title from `01-titles.md`) + their own LinkedIn post | per person | Needed for the content contest |
| 11 | Submit the form: https://forms.gle/cD7fCnPnkdVm2sH78 | 5 min | |

## Verify before recording (this part has not been run against live Hindsight yet)

The code is unit-tested and contract-tested against the Hindsight REST shapes. It has **not** yet run against a live Hindsight instance or Groq, because the build environment had no network access to either. Check these on the first live run:

- [ ] Suresh "with memory" avoids a per-watt price and mentions the RWA template. If it doesn't, check that the playbook panel has content (wait for consolidation, or click Refresh), then re-draft.
- [ ] Padma "with memory" comes out in Telugu. The prompt says to use Telugu *if the lead prefers it*. The preference comes from recalled memory ("Speaks Telugu").
- [ ] *Due now* lists Mohammed Irfan (today after 6pm) and Rahul Mehta (Monday after the vote). If structured output comes back empty, the panel falls back to reflect's text answer.
- [ ] The weeks 1–2 → full history replay shows the playbook visibly growing. Consolidation is asynchronous, so allow 30–90 s after seeding.
- [ ] Drafts take a few seconds on Groq. If Groq returns 429 (free-tier rate limit), wait and retry, or set `LLM_MODEL=openai/gpt-oss-20b`.

If any of these fail, send me the error or output and I'll fix it.

## Rules that disqualify content
- The word "hackathon" anywhere in the article, social post or hashtags. (Checked: none of the drafts contain it.)
- An article or video shared only as a Google Drive link.
- A private video or article.

## Why this project should score well (mapped to the judging criteria)

| Criterion (weight) | What Pakka shows |
|---|---|
| Innovation (30%) | Not a chatbot. It learns cross-lead sales rules from outcomes, in an Indian SMB context (WhatsApp, RWA, PM Surya Ghar, Telugu) that judges won't have seen ten times |
| Hindsight memory (25%) | Uses retain with tags + timestamps, strict-scoped recall, reflect, reflect with a JSON schema, observations, and a self-refreshing mental model. Plus a visible before/after and a staged learning curve |
| Technical (20%) | Clean modules, tests incl. a Hindsight contract test, no fragile tool calls, JSON retries, offline mode |
| UX (15%) | One screen: side-by-side drafts, cited memories, playbook, due list |
| Impact (10%) | Telecallers cost ₹10–25k/month. Indian lead-follow-up CRMs (Kylas ₹12,999/mo, TeleCRM ₹799/user/mo) show that SMBs already pay for follow-up tooling. None of them learn which follow-ups close |

Honest caveats if a judge asks: the data is synthetic. Outcome logging is manual today (the next step is WhatsApp Business API webhooks). And the learning quality depends on reps logging outcomes, which is the actual adoption risk.
