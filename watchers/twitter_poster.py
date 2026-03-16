"""
twitter_poster.py - Posts to X (Twitter) via Playwright browser automation (Gold Tier).

Uses cookie-based session (no persistent profile lock issues).
On first run use --setup to log in manually and save cookies.

Usage:
    python twitter_poster.py --setup     (opens browser, you log in, cookies saved)
    python twitter_poster.py --post      (JSON via stdin: {"content": "..."})
    python twitter_poster.py --test-login

Env vars required:
    TWITTER_EMAIL, TWITTER_PASSWORD

Optional:
    DRY_RUN (default: true)
"""

import json
import logging
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

TWITTER_EMAIL    = os.getenv("TWITTER_EMAIL", "")
TWITTER_PASSWORD = os.getenv("TWITTER_PASSWORD", "")
DRY_RUN          = os.getenv("DRY_RUN", "true").lower() == "true"

COOKIES_FILE = Path(__file__).parent.parent / "AI_Employee_Vault" / "Logs" / ".twitter_cookies.json"
MAX_TWEET_LENGTH = 280

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Twitter] %(levelname)s: %(message)s",
)
logger = logging.getLogger("Twitter")


def get_browser(p):
    from playwright.sync_api import sync_playwright
    chrome_path = os.getenv("CHROME_PATH", r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    browser = p.chromium.launch(
        executable_path=chrome_path if chrome_path and Path(chrome_path).exists() else None,
        headless=False,
        args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
    )
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 800},
        locale="en-US",
    )
    context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
    return browser, context


def load_cookies(context):
    if COOKIES_FILE.exists():
        cookies = json.loads(COOKIES_FILE.read_text())
        context.add_cookies(cookies)
        logger.info(f"Loaded {len(cookies)} saved cookies.")
        return True
    return False


def save_cookies(context):
    COOKIES_FILE.parent.mkdir(exist_ok=True)
    COOKIES_FILE.write_text(json.dumps(context.cookies()))
    logger.info("Cookies saved.")


def is_logged_in(page):
    return "x.com/home" in page.url or "twitter.com/home" in page.url


def setup(context, page):
    """Open browser for manual login, save cookies when done."""
    load_cookies(context)
    page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2000)

    if is_logged_in(page):
        logger.info("Already logged in.")
        save_cookies(context)
        return

    logger.warning("ACTION REQUIRED: Log in to X.com in the browser window. Waiting up to 3 minutes...")
    page.goto("https://x.com/login", wait_until="domcontentloaded", timeout=30000)
    for _ in range(180):
        page.wait_for_timeout(1000)
        if is_logged_in(page):
            break
    else:
        raise Exception("Login timed out.")

    save_cookies(context)
    logger.info("Login successful. Cookies saved.")


def post_tweet(context, page, content: str):
    if not COOKIES_FILE.exists():
        raise Exception("No saved cookies. Run: python twitter_poster.py --setup")

    load_cookies(context)
    page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2000)

    if not is_logged_in(page):
        raise Exception("Not logged in. Run: python twitter_poster.py --setup")

    logger.info("Opening tweet composer...")
    post_btn_nav = page.locator('[data-testid="SideNav_NewTweet_Button"]')
    try:
        post_btn_nav.wait_for(state="visible", timeout=10000)
        post_btn_nav.click()
    except Exception:
        logger.warning("Sidebar Post button not found, falling back to /compose/tweet")
        page.goto("https://x.com/compose/tweet", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2000)

    tweet_box = page.locator('[data-testid="tweetTextarea_0"]').first
    tweet_box.wait_for(timeout=15000)
    tweet_box.click()
    page.wait_for_timeout(300)
    page.keyboard.type(content, delay=50)

    # Poll until Post button is enabled (avoids eval/CSP issues)
    post_btn = page.locator('[data-testid="tweetButtonInline"]').first
    for _ in range(20):
        if post_btn.get_attribute("aria-disabled") != "true":
            break
        page.wait_for_timeout(500)

    # tweet_box.press() focuses + sends key atomically — overlay-proof
    tweet_box.press("Control+Enter")
    page.wait_for_timeout(4000)

    save_cookies(context)
    logger.info("Tweet posted successfully.")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--setup", action="store_true", help="Log in manually and save cookies")
    parser.add_argument("--post", action="store_true", help="Post content from stdin JSON")
    parser.add_argument("--test-login", action="store_true", help="Alias for --setup")
    args = parser.parse_args()

    if not args.setup and not args.post and not args.test_login:
        print("Usage: python twitter_poster.py --setup | --post")
        sys.exit(1)

    content = ""
    if args.post:
        raw = sys.stdin.read()
        try:
            content = json.loads(raw).get("content", "")
        except Exception:
            print(json.dumps({"success": False, "error": "Invalid JSON input"}))
            sys.exit(1)
        if not content:
            print(json.dumps({"success": False, "error": "No content provided"}))
            sys.exit(1)
        if len(content) > MAX_TWEET_LENGTH:
            print(json.dumps({"success": False, "error": f"Tweet too long: {len(content)}/{MAX_TWEET_LENGTH}"}))
            sys.exit(1)
        if DRY_RUN:
            logger.info(f"[DRY RUN] Would post: {content}")
            print(json.dumps({"success": True, "dry_run": True}))
            return

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(json.dumps({"success": False, "error": "Run: pip install playwright && python -m playwright install chromium"}))
        sys.exit(1)

    with sync_playwright() as p:
        browser, context = get_browser(p)
        page = context.new_page()
        try:
            if args.setup or args.test_login:
                setup(context, page)
                print(json.dumps({"success": True, "message": "Login successful, cookies saved"}))
            else:
                post_tweet(context, page, content)
                print(json.dumps({"success": True}))
        except Exception as e:
            logger.error(f"Error: {e}")
            print(json.dumps({"success": False, "error": str(e)}))
            sys.exit(1)
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    main()
