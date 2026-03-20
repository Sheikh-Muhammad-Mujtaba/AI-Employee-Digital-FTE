# Facebook Post Queue

Add Facebook posts here. The facebook_watcher.py checks this file every 5 minutes.

**TWO MODES SUPPORTED:**

## Mode 1: Topic-Based (AI Drafts) ⭐ RECOMMENDED

You provide the topic, AI writes the full post.

```
### [POST_TITLE]
- status: pending
- scheduled_for: YYYY-MM-DD HH:MM
- topic: {Your topic/idea - AI will draft post from this}
- tone: professional | casual | educational | thought-leadership
```

## Mode 2: Content-Based (You Write)

You write the full post, AI just posts.

```
### [POST_TITLE]
- status: scheduled
- scheduled_for: YYYY-MM-DD HH:MM
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

### Test_AI_Draft_FB_001
- status: pending
- scheduled_for: 2026-03-19 17:00
- topic: Testing our AI Employee's ability to draft Facebook posts from just a topic idea. Let's see how well it handles longer form content!
- tone: casual

### Platinum_Tier_Demo
- status: pending
- scheduled_for: 2026-03-19 18:00
- topic: Live demo of our Platinum Tier AI Employee! It's drafting this post automatically from just a topic idea on all
  platforms - LinkedIn, Twitter, Facebook, and Instagram!
- tone: professional

---

## Examples

### Topic-Based (AI Drafts):

```
### My_First_FB_Post
- status: pending
- scheduled_for: 2026-03-20 10:00
- topic: Excited to announce our Platinum Tier AI Employee with Cloud + Local architecture. It monitors Gmail 24/7, drafts social posts, and integrates with ERPNext - all with human approval!
- tone: professional
```

### Content-Based (You Write):

```
### Product_Update
- status: scheduled
- scheduled_for: 2026-03-21 11:00
- content: |
    🎉 New Feature Alert!
    
    Our AI Employee can now:
    ✅ Draft posts from topics (AI writes for you)
    ✅ Monitor Gmail 24/7
    ✅ Sync with ERPNext
    ✅ Auto-approve routine tasks
    
    Book a demo: link.com/demo
- hashtags: #AI #Automation #ProductUpdate
```
