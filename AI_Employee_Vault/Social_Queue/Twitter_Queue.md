# Twitter/X Post Queue

Add tweets here. The twitter_watcher.py checks this file every 5 minutes.

**TWO MODES SUPPORTED:**

## Mode 1: Topic-Based (AI Drafts) ⭐ RECOMMENDED

You provide the topic, AI writes the full tweet.

```
### [POST_TITLE]
- status: pending
- scheduled_for: YYYY-MM-DD HH:MM
- topic: {Your topic/idea - AI will draft tweet from this}
- tone: professional | casual | educational | thought-leadership
```

## Mode 2: Content-Based (You Write)

You write the full tweet, AI just posts.

```
### [POST_TITLE]
- status: scheduled
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

### Test_AI_Draft_001
- status: pending
- scheduled_for: 2026-03-19 17:00
- topic: Testing our AI Employee's ability to draft tweets from just a topic idea. Let's see how well it works!
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
### My_First_AI_Tweet
- status: pending
- scheduled_for: 2026-03-20 09:00
- topic: Just discovered our AI Employee can now draft social media posts automatically. This is a game changer for content creation!
- tone: casual
```

### Content-Based (You Write):

```
### Product_Launch
- status: scheduled
- scheduled_for: 2026-03-21 10:00
- content: |
    🚀 Exciting news! Our Platinum Tier AI Employee is now available.
    
    Features:
    ✅ 24/7 email monitoring
    ✅ Social media automation
    ✅ ERPNext integration
    ✅ Human-in-the-loop approval
    
    Book a demo today!
- hashtags: #AI #Automation #ProductLaunch
```
