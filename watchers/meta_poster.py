"""
meta_poster.py - Posts to Facebook and Instagram via Playwright (Gold Tier).

Facebook and Instagram share the same Meta login — one persistent Chrome profile
covers both platforms.

Usage:
    python meta_poster.py --platform facebook --post   (JSON via stdin)
    python meta_poster.py --platform instagram --post  (JSON via stdin: requires image_url)
    python meta_poster.py --platform facebook --test-login

Stdin JSON:
    Facebook:  {"content": "Your post text"}
    Instagram: {"content": "Your caption", "image_url": "https://..."}

Env vars required:
    FACEBOOK_EMAIL, FACEBOOK_PASSWORD

Optional:
    FACEBOOK_HEADLESS (default: false)
    DRY_RUN           (default: true)
"""

import argparse
import json
import logging
import os
import sys
import tempfile
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

FACEBOOK_EMAIL    = os.getenv("FACEBOOK_EMAIL", "")
FACEBOOK_PASSWORD = os.getenv("FACEBOOK_PASSWORD", "")
FACEBOOK_HEADLESS = os.getenv("FACEBOOK_HEADLESS", "false").lower() == "true"
DRY_RUN           = os.getenv("DRY_RUN", "true").lower() == "true"

PROFILE_DIR = Path(__file__).parent.parent / "AI_Employee_Vault" / "Logs" / ".meta_profile"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Meta] %(levelname)s: %(message)s",
)
logger = logging.getLogger("Meta")


# ── Helpers ────────────────────────────────────────────────────────────────────

def download_image(url: str) -> str:
    """Download image to a temp file, return the file path."""
    try:
        import httpx
    except ImportError:
        raise RuntimeError("httpx not installed. Run: pip install httpx")

    suffix = "." + url.split("?")[0].split(".")[-1] if "." in url.split("/")[-1] else ".jpg"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        tmp.write(resp.content)
    tmp.close()
    logger.info(f"Image downloaded to temp: {tmp.name}")
    return tmp.name


def is_logged_in_facebook(page) -> bool:
    return "facebook.com" in page.url and "/login" not in page.url and "checkpoint" not in page.url


def is_logged_in_instagram(page) -> bool:
    return "instagram.com" in page.url and "/accounts/login" not in page.url


# ── Login ──────────────────────────────────────────────────────────────────────

def login_facebook(page):
    logger.info("Checking Facebook login...")
    page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2000)

    if is_logged_in_facebook(page):
        logger.info("Already logged in to Facebook.")
        return

    logger.info("Logging in to Facebook...")
    page.locator('#email').fill(FACEBOOK_EMAIL)
    page.locator('#pass').fill(FACEBOOK_PASSWORD)
    page.locator('[name="login"]').click()
    page.wait_for_timeout(4000)

    if not is_logged_in_facebook(page):
        logger.warning(f"Extra verification needed (URL: {page.url}). Complete it in the browser. Waiting up to 2 minutes...")
        for _ in range(120):
            page.wait_for_timeout(1000)
            if is_logged_in_facebook(page):
                break
        else:
            raise Exception(f"Facebook login timed out. Still on: {page.url}")

    logger.info("Facebook login successful.")


def login_instagram(page):
    """Instagram uses Meta account — try direct login to instagram.com."""
    logger.info("Checking Instagram login...")
    page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2000)

    if is_logged_in_instagram(page):
        logger.info("Already logged in to Instagram.")
        return

    logger.info("Logging in to Instagram...")
    page.locator('input[name="username"]').fill(FACEBOOK_EMAIL)
    page.locator('input[name="password"]').fill(FACEBOOK_PASSWORD)
    page.locator('[type="submit"]').click()
    page.wait_for_timeout(4000)

    # Dismiss "Save login info" or "Turn on notifications" prompts
    for label in ["Save info", "Not Now", "Not now"]:
        try:
            page.get_by_role("button", name=label).click(timeout=3000)
            page.wait_for_timeout(1000)
        except Exception:
            pass

    if not is_logged_in_instagram(page):
        logger.warning(f"Extra verification needed (URL: {page.url}). Complete it in the browser. Waiting up to 2 minutes...")
        for _ in range(120):
            page.wait_for_timeout(1000)
            if is_logged_in_instagram(page):
                break
        else:
            raise Exception(f"Instagram login timed out. Still on: {page.url}")

    logger.info("Instagram login successful.")


# ── Post: Facebook ─────────────────────────────────────────────────────────────

def post_facebook(page, content: str):
    logger.info("Opening Facebook feed...")
    page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)

    # Click the "What's on your mind?" prompt to open the composer modal
    composer_selectors = [
        '[aria-label="What\'s on your mind?"]',
        'div[aria-placeholder="What\'s on your mind?"]',
        '[placeholder="What\'s on your mind?"]',
        'div[role="button"]:has-text("What\'s on your mind")',
        'span:has-text("What\'s on your mind")',
    ]
    clicked = False
    for sel in composer_selectors:
        try:
            page.locator(sel).first.click(timeout=5000)
            clicked = True
            logger.info(f"Opened composer with: {sel}")
            break
        except Exception:
            continue

    if not clicked:
        raise Exception("Could not open Facebook post composer — UI may have changed.")

    page.wait_for_timeout(2000)

    # Type into the modal editor (Facebook uses Lexical editor)
    editor_selectors = [
        'div[data-lexical-editor="true"]',
        'div[contenteditable="true"][data-lexical-editor="true"]',
        '[contenteditable="true"][aria-placeholder="What\'s on your mind?"]',
        '[contenteditable="true"][role="textbox"]',
        'div[contenteditable="true"][spellcheck="true"]',
        'div[contenteditable="true"]',
    ]
    typed = False
    for sel in editor_selectors:
        try:
            el = page.locator(sel).first
            el.wait_for(state="visible", timeout=3000)
            el.click()
            page.wait_for_timeout(300)
            page.keyboard.type(content, delay=20)
            typed = True
            logger.info(f"Typed content with: {sel}")
            break
        except Exception:
            continue

    if not typed:
        raise Exception("Could not type into Facebook post editor.")

    page.wait_for_timeout(1000)

    # Click the Post button
    post_selectors = [
        '[aria-label="Post"]',
        'div[aria-label="Post"]',
        'div[role="button"]:has-text("Post")',
        'span:has-text("Post")',
    ]
    posted = False
    for sel in post_selectors:
        try:
            page.locator(sel).last.click(timeout=5000)
            posted = True
            break
        except Exception:
            continue

    if not posted:
        raise Exception("Could not find Facebook Post button.")

    page.wait_for_timeout(3000)
    logger.info("Facebook post published.")


# ── Post: Instagram ────────────────────────────────────────────────────────────

def post_instagram(page, content: str, image_url: str):
    if not image_url:
        raise Exception("Instagram posts require an image_url. Add image_url to your Instagram_Queue.md entry.")

    # Download image first (fail fast before opening browser)
    image_path = download_image(image_url)

    logger.info("Opening Instagram...")
    page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)

    # Dismiss "Save your login info" one-tap prompt if present
    for label in ["Save info", "Not Now", "Not now", "Continue", "Turn on"]:
        try:
            page.get_by_role("button", name=label).click(timeout=2000)
            page.wait_for_timeout(1000)
            logger.info(f"Dismissed prompt: {label}")
        except Exception:
            pass

    # Dismiss any notification prompts
    for label in ["Not Now", "Not now"]:
        try:
            page.get_by_role("button", name=label).click(timeout=2000)
            page.wait_for_timeout(1000)
        except Exception:
            pass

    # Click the Create (+) button in the sidebar
    create_selectors = [
        '[aria-label="Create"]',
        'svg[aria-label="Create"]',
        'a[href="/create/select/"]',
        '[aria-label="New post"]',
        'span:has-text("Create")',
    ]
    clicked = False
    for sel in create_selectors:
        try:
            page.locator(sel).first.click(timeout=5000)
            clicked = True
            logger.info(f"Clicked Create button with: {sel}")
            break
        except Exception:
            continue

    if not clicked:
        raise Exception("Could not find Instagram Create button.")

    page.wait_for_timeout(2000)

    # Click "Select from computer" button to trigger file input
    for label in ["Select from computer", "Select From Computer"]:
        try:
            page.get_by_role("button", name=label).click(timeout=5000)
            logger.info("Clicked 'Select from computer'")
            page.wait_for_timeout(1000)
            break
        except Exception:
            pass

    # Upload image via file input
    file_input = page.locator('input[type="file"]').first
    file_input.set_input_files(image_path, timeout=15000)
    page.wait_for_timeout(3000)

    # Click Next: Crop screen → Filter screen → Caption screen (exactly 2 clicks)
    for i in range(2):
        page.get_by_role("button", name="Next").click(timeout=10000)
        logger.info(f"Clicked Next ({i+1})")
        page.wait_for_timeout(2500)

    # Write caption — wait for caption screen to load
    page.wait_for_timeout(1000)
    caption_selectors = [
        '[aria-label="Write a caption..."]',
        'textarea[aria-label="Write a caption..."]',
        '[placeholder="Write a caption..."]',
        'div[contenteditable="true"][aria-label="Write a caption..."]',
        'div[role="textbox"]',
    ]
    caption_typed = False
    for sel in caption_selectors:
        try:
            el = page.locator(sel).first
            el.wait_for(state="visible", timeout=5000)
            el.click()
            page.wait_for_timeout(300)
            page.keyboard.type(content, delay=20)
            caption_typed = True
            logger.info(f"Typed caption with: {sel}")
            break
        except Exception:
            continue

    if not caption_typed:
        logger.warning("Could not type caption — posting without it.")

    page.wait_for_timeout(1000)

    # Share
    try:
        page.get_by_role("button", name="Share").click(timeout=5000)
    except Exception:
        raise Exception("Could not find Instagram Share button.")

    page.wait_for_timeout(5000)
    logger.info("Instagram post published.")

    # Clean up temp image
    try:
        os.unlink(image_path)
    except Exception:
        pass


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AI Employee — Meta Poster (Facebook + Instagram)")
    parser.add_argument("--platform", required=True, choices=["facebook", "instagram"])
    parser.add_argument("--post", action="store_true")
    parser.add_argument("--test-login", action="store_true")
    args = parser.parse_args()

    if not args.post and not args.test_login:
        print("Usage: python meta_poster.py --platform facebook|instagram --post | --test-login")
        sys.exit(1)

    if not FACEBOOK_EMAIL or not FACEBOOK_PASSWORD:
        print(json.dumps({"success": False, "error": "FACEBOOK_EMAIL and FACEBOOK_PASSWORD must be set in .env"}))
        sys.exit(1)

    content = ""
    image_url = ""
    if args.post:
        raw = sys.stdin.read()
        try:
            data = json.loads(raw)
            content = data.get("content", "")
            image_url = data.get("image_url", "")
        except Exception:
            print(json.dumps({"success": False, "error": "Invalid JSON input"}))
            sys.exit(1)
        if not content:
            print(json.dumps({"success": False, "error": "No content provided"}))
            sys.exit(1)

        if DRY_RUN:
            logger.info(f"[DRY_RUN] Would post to {args.platform}:\n{content}")
            print(json.dumps({"success": True, "dry_run": True}))
            return

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(json.dumps({"success": False, "error": "Playwright not installed. Run: pip install playwright && python -m playwright install chromium"}))
        sys.exit(1)

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    chrome_path = os.getenv("CHROME_PATH", r"C:\Program Files\Google\Chrome\Application\chrome.exe")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            executable_path=chrome_path if chrome_path and Path(chrome_path).exists() else None,
            headless=FACEBOOK_HEADLESS,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            locale="en-US",
        )
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
        page = context.new_page()

        try:
            if args.platform == "facebook":
                login_facebook(page)
                if args.test_login:
                    print(json.dumps({"success": True, "message": "Facebook login OK"}))
                else:
                    post_facebook(page, content)
                    print(json.dumps({"success": True}))

            elif args.platform == "instagram":
                login_instagram(page)
                if args.test_login:
                    print(json.dumps({"success": True, "message": "Instagram login OK"}))
                else:
                    post_instagram(page, content, image_url)
                    print(json.dumps({"success": True}))

        except Exception as e:
            logger.error(f"Error: {e}")
            print(json.dumps({"success": False, "error": str(e)}))
            sys.exit(1)
        finally:
            context.close()


if __name__ == "__main__":
    main()
