# Instagram Post Queue

Add Instagram posts here. The facebook_watcher.py checks this file every 5 minutes.

**TWO MODES SUPPORTED:**

## Mode 1: Topic-Based (AI Drafts) ⭐ RECOMMENDED

You provide the topic and image, AI writes the caption.

```
### [POST_TITLE]
- status: pending
- scheduled_for: YYYY-MM-DD HH:MM
- image_url: https://example.com/image.png (required)
- topic: {Your topic/idea - AI will draft caption from this}
- tone: professional | casual | inspirational
```

## Mode 2: Content-Based (You Write)

You write the full caption, AI just posts.

```
### [POST_TITLE]
- status: scheduled
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

### Test_AI_Draft_IG_001
- status: pending
- scheduled_for: 2026-03-19 17:00
- image_url: https://example.com/demo-image.png
- topic: Testing our AI Employee's ability to draft Instagram captions from just a topic. Perfect for visual storytelling!
- tone: inspirational

---

## Examples

### Topic-Based (AI Drafts Caption):

```
### AI_Product_Demo
- status: pending
- scheduled_for: 2026-03-20 12:00
- image_url: https://example.com/product-demo.png
- topic: Showing our Platinum Tier AI Employee in action. It drafts posts, monitors email, and syncs with ERPNext - all while you focus on what matters!
- tone: professional
```

### Content-Based (You Write Caption):

```
### Behind_The_Scenes
- status: scheduled
- scheduled_for: 2026-03-21 14:00
- image_url: https://example.com/office-photo.png
- content: |
    📸 Behind the scenes at our AI lab!
    
    Our team is building the future of work:
    ✨ AI Employees that work 24/7
    ✨ Cloud + Local hybrid architecture
    ✨ Human-in-the-loop approval
    
    Want to see it in action? Link in bio!
- hashtags: #AI #Tech #Innovation #FutureOfWork
```

---

## Instagram Tips

- **Image Required:** Instagram posts MUST include an image_url
- **Aspect Ratio:** Use 1:1 (square) or 4:5 (portrait) for best results
- **Hashtags:** Instagram allows up to 30 hashtags (use 5-15 for best engagement)
- **Caption Length:** Up to 2,200 characters (but shorter is better)
