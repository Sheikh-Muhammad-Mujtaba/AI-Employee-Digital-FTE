# LinkedIn Post Queue
---
last_updated: 2026-02-21
managed_by: AI Employee (Silver Tier)
---

The LinkedIn watcher (`watchers/linkedin_watcher.py`) reads this file every 5 minutes.
Add posts below using the format shown. Set `status: pending` for posts you want scheduled.

**Status values:**
- `pending`   — waiting to be triggered at scheduled time
- `triggered` — action file created in /Needs_Action (Claude will draft/refine)
- `approved`  — post approved and queued for publishing
- `published` — live on LinkedIn
- `skipped`   — manually cancelled

---

## Post: Introduction to Our AI Employee Project

- scheduled: 2026-02-24T08:00:00
- topic: We're building a local-first AI Employee using Claude Code and Obsidian. Here's what we've learned in the first two weeks — 3 unexpected insights about autonomous agents.
- tone: thought-leadership
- status: pending

---

## Post: Why Local-First AI Matters in 2026

- scheduled: 2026-02-27T09:00:00
- topic: Every AI tool wants your data in the cloud. We chose a different path — 100% local, privacy-first automation. Here's why that decision changed everything about how we build.
- tone: professional
- status: pending

---

## Post: The Real Cost of a Digital FTE vs Human Employee

- scheduled: 2026-03-03T08:30:00
- topic: A human FTE costs $4k-$8k/month for 2,000 hours of work. A Digital FTE costs $500-$2k/month for 8,760 hours. The math is undeniable — but there's a nuance most people miss.
- tone: educational
- status: pending

---

<!--
ADD NEW POSTS BELOW THIS LINE.

## Post: {Your Post Title}

- scheduled: YYYY-MM-DDTHH:MM:SS
- topic: {Describe the angle/hook for this post. Be specific — the AI will expand on this.}
- tone: professional | thought-leadership | achievement | educational
- status: pending
-->
