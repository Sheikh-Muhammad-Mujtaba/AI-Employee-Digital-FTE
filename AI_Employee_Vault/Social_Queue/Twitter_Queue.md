# Twitter/X Post Queue

Add tweets here. The twitter_watcher.py checks this file every 5 minutes.
Set `status: scheduled` and a `scheduled_for` date to queue a post.

---

## Format

```
### [POST_TITLE]
- status: scheduled | posted | draft
- scheduled_for: YYYY-MM-DD HH:MM
- content: |
    Your tweet text here (max 280 chars)
- hashtags: #tag1 #tag2
```

---

## Queue

### Welcome_Tweet_001
- status: posted
- scheduled_for: 2026-03-15 09:00
- content: |
    Excited to share what we've been building — a Personal AI Employee that manages emails, social media, and business finances autonomously. Powered by Claude Code. 🤖
- hashtags: #AI #Automation #ClaudeCode

### Gold_Tier_Launch_001
- status: triggered
- scheduled_for: 2026-03-15 08:00
- content: |
    We built a Personal AI Employee in 48 hours — it reads emails, drafts replies, posts to social media, and tracks finances. All autonomous. All local. 🤖
- hashtags: #AI #BuildInPublic #ClaudeCode #Automation
