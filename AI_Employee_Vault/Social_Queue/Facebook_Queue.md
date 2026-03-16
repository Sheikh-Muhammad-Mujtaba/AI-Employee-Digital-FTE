# Facebook Post Queue

Add Facebook posts here. The facebook_watcher.py checks this file every 5 minutes.

---

## Format

```
### [POST_TITLE]
- status: scheduled | posted | draft
- scheduled_for: YYYY-MM-DD HH:MM
- page_id: your_page_id (optional, defaults to env FB_PAGE_ID)
- content: |
    Your post text here
- hashtags: #tag1 #tag2
```

---

## Queue

### Launch_Announcement_001
- status: draft
- scheduled_for: 2026-03-16 10:00
- content: |
    Big news! Our Personal AI Employee is live. It reads your emails, schedules your social posts, tracks your finances in Odoo, and sends you a CEO briefing every Monday morning. All local-first, all yours.
- hashtags: #AI #Productivity #Automation
