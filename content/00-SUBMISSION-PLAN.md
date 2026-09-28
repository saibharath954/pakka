# Submission plan (deadline 29 Sep)

The form needs: repo link, LinkedIn post, article, video, Reddit post, feedback. **Every team member** also fills the profile form (https://forms.gle/AXWnanWsEEir6xSP9).

## Tonight, in order

| # | Task | Time |
|---|---|---|
| 1 | Hindsight Cloud: sign up, apply the promo code under Billing, create an API key. Groq: create a key. Put both in `.env` | 15 min |
| 2 | `pip install -r requirements.txt && python scripts/smoke.py` | 5 min |
| 3 | `python scripts/replay.py`: teaches the bank 8 weeks of orders against live Hindsight and writes `data/learning_curve.json` | 10–25 min |
| 4 | `uvicorn munshi.app:app`, then walk the 5-step demo in the README | 20 min |
| 5 | Re-take the screenshots in `docs/` from the live run, and update the README numbers if the live curve differs | 15 min |
| 6 | Record the team video (`05-video-script.md`) and upload it to YouTube as **Public**, with the thumbnail | 60–90 min |
| 7 | Edit the article (`02-article.md`) into your own voice, add the screenshots, and publish on Dev.to, Hashnode or Medium | 45 min |
| 8 | LinkedIn post (`03-linkedin-post.md`): article link as the first comment, Hindsight link as the second | 10 min |
| 9 | Reddit link post (`04-reddit-post.md`) | 5 min |
| 10 | Each teammate: their own article from a different angle (use `01-titles.md`), plus their own LinkedIn post | per person |
| 11 | Submit: https://forms.gle/cD7fCnPnkdVm2sH78 | 5 min |

## Check on the first live run

Everything is tested offline and against a stub of the Hindsight API. It has **not yet run against live Hindsight Cloud or Groq**, because the build environment couldn't reach either. Check:

- [ ] `replay.py` finishes, and the "with memory" curve rises. If it stays flat, recall isn't returning the confirmation chunks. Send me the output.
- [ ] In the inbox, Sai Ram Kirana's "blue wala" → Lay's and Sharma Kirana's → Surf Excel, both auto-accepted.
- [ ] Venkat Provisions' "usual list" shows the repeat banner.
- [ ] The ordering dictionary panel fills in (it needs consolidation; click Refresh, then wait 30–60 s).
- [ ] Ask Munshi → "What needs attention?" returns cards. If structured output is empty, it shows reflect's text answer instead.
- [ ] If Groq rate-limits (429) during the demo, set `MUNSHI_PARSER=rules`. The seed messages parse perfectly with the rule parser.

## Disqualifiers
- The word "hackathon" in the article, the post or hashtags. (Checked: none of the drafts contain it; this file isn't one of them.)
- An article or video shared as a Google Drive link. Both must be public.
