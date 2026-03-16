# Instagram Post Queue

Add Instagram posts here. The facebook_watcher.py (Instagram Graph API) checks this file every 5 minutes.

---

## Format

```
### [POST_TITLE]
- status: scheduled | posted | draft
- scheduled_for: YYYY-MM-DD HH:MM
- image_url: https://... (required for Instagram)
- content: |
    Your caption here
- hashtags: #tag1 #tag2 #tag3
```

---

## Queue

### Launch_Reel_001
- status: draft
- scheduled_for: 2026-03-16 11:00
- image_url: https://example.com/launch-graphic.png
- content: |
    Meet your new AI Employee. It never sleeps, never misses an email, and sends you a full business report every Monday. Built with Claude Code + Obsidian.
- hashtags: #AI #Tech #Startup #Automation #ClaudeCode
