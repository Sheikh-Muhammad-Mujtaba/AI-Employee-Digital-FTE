"""
linkedin_poster.py - Posts to LinkedIn via Playwright browser automation (Silver Tier).

Usage:
    python linkedin_poster.py --post       (JSON via stdin: {"content": "..."})
    python linkedin_poster.py --test-login (verify credentials only)

Env vars required:
    LINKEDIN_EMAIL, LINKEDIN_PASSWORD

Optional:
    LINKEDIN_HEADLESS (default: true)
    DRY_RUN (default: true)
"""

import argparse
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

LINKEDIN_EMAIL    = os.getenv("LINKEDIN_EMAIL", "")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD", "")
LINKEDIN_HEADLESS = os.getenv("LINKEDIN_HEADLESS", "true").lower() == "true"
DRY_RUN           = os.getenv("DRY_RUN", "true").lower() == "true"
COOKIES_FILE      = Path(__file__).parent.parent / "AI_Employee_Vault" / "Logs" / ".linkedin_cookies.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [LinkedIn] %(levelname)s: %(message)s",
)
logger = logging.getLogger("LinkedIn")


# ── Cookie helpers ─────────────────────────────────────────────────────────────

def save_cookies(context):
    cookies = context.cookies()
    COOKIES_FILE.parent.mkdir(exist_ok=True)
    COOKIES_FILE.write_text(json.dumps(cookies))
    logger.info(f"Saved {len(cookies)} session cookies.")


def load_cookies(context):
    if COOKIES_FILE.exists():
        cookies = json.loads(COOKIES_FILE.read_text())
        context.add_cookies(cookies)
        logger.info(f"Loaded {len(cookies)} saved cookies.")
        return True
    return False


# ── Login ──────────────────────────────────────────────────────────────────────

def is_logged_in(page) -> bool:
    """Returns True only if we're on an actual feed/home page, not a login redirect."""
    url = page.url
    return (
        "linkedin.com/feed" in url
        and "login" not in url
        and "session_redirect" not in url
        and "signin" not in url
    )


def login(page, context):
    logger.info("Checking login status...")
    page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)

    if is_logged_in(page):
        logger.info("Already logged in via saved cookies.")
        return

    logger.info(f"Not logged in (landed on: {page.url}). Please log in manually in the browser window.")
    page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=30000)
    logger.warning("ACTION REQUIRED: Log in to LinkedIn in the browser window (use 'Continue with Google'). Waiting up to 3 minutes...")

    if "checkpoint" in page.url or "challenge" in page.url or "verify" in page.url or not is_logged_in(page):
        logger.warning("LinkedIn verification required. Complete it in the browser window. Waiting up to 3 minutes...")
        # Poll until we land on the feed or timeout
        for _ in range(180):
            page.wait_for_timeout(1000)
            if is_logged_in(page):
                break
        else:
            screenshot_path = COOKIES_FILE.parent / "linkedin_login_debug.png"
            page.screenshot(path=str(screenshot_path))
            raise Exception(f"Login timed out — still on: {page.url}")

    if not is_logged_in(page):
        screenshot_path = COOKIES_FILE.parent / "linkedin_login_debug.png"
        page.screenshot(path=str(screenshot_path))
        raise Exception(f"Login failed — landed on: {page.url}. Check LINKEDIN_EMAIL and LINKEDIN_PASSWORD in .env")

    logger.info("Login successful.")


# ── Post ───────────────────────────────────────────────────────────────────────

def create_post(page, content: str):
    logger.info("Opening LinkedIn feed...")
    page.goto("https://www.linkedin.com/feed/", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(4000)

    # Dismiss any popups/modals
    for dismiss_sel in ['button[aria-label="Dismiss"]', 'button:has-text("Skip")', 'button:has-text("Not now")']:
        try:
            page.click(dismiss_sel, timeout=2000)
            page.wait_for_timeout(1000)
        except Exception:
            pass

    # Click "Start a post"
    logger.info("Clicking 'Start a post'...")

    # Try JS-based click first — most reliable across UI versions
    clicked = page.evaluate("""() => {
        const candidates = [
            ...document.querySelectorAll('button'),
            ...document.querySelectorAll('[role="button"]'),
        ];
        for (const el of candidates) {
            const text = (el.innerText || el.getAttribute('aria-label') || '').toLowerCase();
            if (text.includes('start a post') || text.includes('share') && el.closest('.share-box')) {
                el.click();
                return true;
            }
        }
        return false;
    }""")

    if not clicked:
        post_btn_selectors = [
            'button[aria-label="Start a post"]',
            'button:has-text("Start a post")',
            '[data-placeholder="Start a post"]',
            '.share-creation-state__trigger',
            '.share-box-feed-entry__trigger',
            '[data-control-name="share.sharebox_text"]',
        ]
        for sel in post_btn_selectors:
            try:
                page.click(sel, timeout=5000)
                clicked = True
                logger.info(f"Clicked 'Start a post' with selector: {sel}")
                break
            except Exception:
                continue

    if not clicked:
        screenshot_path = COOKIES_FILE.parent / "linkedin_debug.png"
        page.screenshot(path=str(screenshot_path))
        logger.error(f"Screenshot saved to: {screenshot_path}")
        raise Exception("Could not find 'Start a post' button — LinkedIn UI may have changed.")

    page.wait_for_timeout(2000)

    # Type content into editor
    logger.info("Typing post content...")
    editor_selectors = [
        '.ql-editor',
        '[data-placeholder="What do you want to talk about?"]',
        '[role="textbox"]',
    ]
    typed = False
    for sel in editor_selectors:
        try:
            page.click(sel, timeout=5000)
            page.keyboard.type(content, delay=15)
            typed = True
            break
        except Exception:
            continue
    if not typed:
        raise Exception("Could not find post editor — LinkedIn UI may have changed.")

    page.wait_for_timeout(1500)

    # Click Post button
    logger.info("Submitting post...")
    submit_selectors = [
        '.share-actions__primary-action',
        'button:has-text("Post")',
        '[data-control-name="share.post"]',
    ]
    posted = False
    for sel in submit_selectors:
        try:
            page.click(sel, timeout=5000)
            posted = True
            break
        except Exception:
            continue
    if not posted:
        raise Exception("Could not find Post button — LinkedIn UI may have changed.")

    page.wait_for_timeout(3000)
    logger.info("Post published successfully.")


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AI Employee — LinkedIn Poster (Playwright)")
    parser.add_argument("--post", action="store_true", help="Post content from stdin JSON")
    parser.add_argument("--test-login", action="store_true", help="Test login only")
    args = parser.parse_args()

    if not args.post and not args.test_login:
        print("Usage: python linkedin_poster.py --post | --test-login")
        sys.exit(1)

    if not LINKEDIN_EMAIL or not LINKEDIN_PASSWORD:
        print(json.dumps({"success": False, "error": "LINKEDIN_EMAIL and LINKEDIN_PASSWORD must be set in .env"}))
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

        if DRY_RUN:
            logger.info(f"[DRY RUN] Would post to LinkedIn:\n{content[:200]}")
            print(json.dumps({"success": True, "dry_run": True}))
            return

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(json.dumps({"success": False, "error": "Playwright not installed. Run: pip install playwright && python -m playwright install chromium"}))
        sys.exit(1)

    # Use a persistent profile directory so LinkedIn stays logged in between runs
    profile_dir = COOKIES_FILE.parent / "chrome_profile"
    profile_dir.mkdir(exist_ok=True)

    chrome_path = os.getenv(
        "CHROME_PATH",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    )

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            executable_path=chrome_path if Path(chrome_path).exists() else None,
            headless=False,  # must be False for persistent context login
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
            ],
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            locale="en-US",
        )
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        page = context.new_page()

        try:
            login(page, context)

            if args.test_login:
                logger.info("Login test passed.")
                print(json.dumps({"success": True, "message": "Login successful"}))
            else:
                create_post(page, content)
                print(json.dumps({"success": True}))

        except Exception as e:
            logger.error(f"Error: {e}")
            print(json.dumps({"success": False, "error": str(e)}))
            sys.exit(1)
        finally:
            context.close()


if __name__ == "__main__":
    main()
