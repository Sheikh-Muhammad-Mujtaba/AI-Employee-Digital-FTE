"""
test_watchers.py - Comprehensive test script for AI Employee Watchers

This script tests all watchers and the orchestrator to ensure they're working correctly.

Usage:
    python test_watchers.py --vault AI_Employee_Vault
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path


def test_vault_structure(vault: Path) -> bool:
    """Test 1: Verify vault folder structure exists."""
    print("\n" + "="*60)
    print("TEST 1: Vault Structure")
    print("="*60)
    
    required_folders = [
        "Inbox",
        "Needs_Action",
        "Pending_Approval",
        "Approved",
        "Rejected",
        "Done",
        "Plans",
        "Social_Queue",
        "Briefings",
        "Accounting",
        "Audit_Reports",
        "Logs",
    ]
    
    all_exist = True
    for folder in required_folders:
        folder_path = vault / folder
        if folder_path.exists() and folder_path.is_dir():
            print(f"  ✓ {folder}/")
        else:
            print(f"  ✗ {folder}/ - MISSING")
            all_exist = False
    
    return all_exist


def test_required_files(vault: Path) -> bool:
    """Test 2: Verify required configuration files exist."""
    print("\n" + "="*60)
    print("TEST 2: Required Configuration Files")
    print("="*60)
    
    required_files = [
        "Dashboard.md",
        "Business_Goals.md",
        "Company_Handbook.md",
    ]
    
    all_exist = True
    for file in required_files:
        file_path = vault / file
        if file_path.exists():
            print(f"  ✓ {file}")
        else:
            print(f"  ✗ {file} - MISSING")
            all_exist = False
    
    return all_exist


def test_env_configuration() -> bool:
    """Test 3: Verify .env file and critical configuration."""
    print("\n" + "="*60)
    print("TEST 3: Environment Configuration")
    print("="*60)
    
    env_file = Path(__file__).parent / ".env"
    if not env_file.exists():
        print("  ✗ .env file - MISSING")
        print("  → Copy .env.example to .env and fill in your credentials")
        return False
    
    print("  ✓ .env file exists")
    
    # Check critical env vars
    env_content = env_file.read_text()
    critical_vars = {
        "AGENT": "AI Agent selection (claude/gemini/qwen)",
        "DRY_RUN": "Dry run mode (true/false)",
        "GMAIL_CLIENT_ID": "Gmail OAuth Client ID",
        "GMAIL_CLIENT_SECRET": "Gmail OAuth Client Secret",
        "GMAIL_REFRESH_TOKEN": "Gmail OAuth Refresh Token",
    }
    
    all_configured = True
    for var, description in critical_vars.items():
        if f"{var}=" in env_content:
            # Check if it's not just a placeholder
            line = [l for l in env_content.splitlines() if l.startswith(f"{var}=")]
            if line and "=" in line[0]:
                value = line[0].split("=", 1)[1].strip()
                if value and value != "your_" + var.lower() + "_here":
                    print(f"  ✓ {var} - configured")
                else:
                    print(f"  ⚠ {var} - placeholder value ({description})")
                    all_configured = False
            else:
                print(f"  ⚠ {var} - empty ({description})")
                all_configured = False
        else:
            print(f"  ✗ {var} - NOT FOUND ({description})")
            all_configured = False
    
    return all_configured


def test_needs_action_folder(vault: Path) -> dict:
    """Test 4: Check Needs_Action folder for unprocessed files."""
    print("\n" + "="*60)
    print("TEST 4: Needs_Action Folder Status")
    print("="*60)
    
    needs_action = vault / "Needs_Action"
    if not needs_action.exists():
        print("  ✗ Needs_Action folder - MISSING")
        return {"total": 0, "unprocessed": 0}
    
    md_files = [f for f in needs_action.iterdir() 
                if f.suffix == ".md" and not f.name.startswith(".")]
    
    print(f"  Total action files: {len(md_files)}")
    
    # Check for unprocessed files
    unprocessed = []
    for f in md_files:
        content = f.read_text()
        # Check if file has been processed (should have been moved to Done)
        unprocessed.append(f.name)
    
    if unprocessed:
        print(f"  ⚠ Unprocessed files: {len(unprocessed)}")
        for f in unprocessed[:5]:  # Show first 5
            print(f"    - {f}")
        if len(unprocessed) > 5:
            print(f"    ... and {len(unprocessed) - 5} more")
    else:
        print("  ✓ All files processed")
    
    return {"total": len(md_files), "unprocessed": len(unprocessed)}


def test_pending_approval_folder(vault: Path) -> dict:
    """Test 5: Check Pending_Approval folder for files awaiting human review."""
    print("\n" + "="*60)
    print("TEST 5: Pending_Approval Folder Status")
    print("="*60)
    
    pending_dir = vault / "Pending_Approval"
    if not pending_dir.exists():
        print("  ✗ Pending_Approval folder - MISSING")
        return {"total": 0, "awaiting_approval": 0}
    
    md_files = [f for f in pending_dir.iterdir() 
                if f.suffix == ".md" and not f.name.startswith(".")]
    
    print(f"  Files awaiting approval: {len(md_files)}")
    
    if md_files:
        print("  Files:")
        for f in md_files[:5]:  # Show first 5
            content = f.read_text()
            # Extract action type from frontmatter
            if "action:" in content:
                action = content.split("action:")[1].split("\n")[0].strip()
                print(f"    - {f.name} (action: {action})")
            else:
                print(f"    - {f.name}")
        if len(md_files) > 5:
            print(f"    ... and {len(md_files) - 5} more")
    else:
        print("  ✓ No files pending approval")
    
    return {"total": len(md_files), "awaiting_approval": len(md_files)}


def test_social_queue_files(vault: Path) -> bool:
    """Test 6: Verify social media queue files exist and are properly formatted."""
    print("\n" + "="*60)
    print("TEST 6: Social Media Queue Files")
    print("="*60)
    
    social_queue = vault / "Social_Queue"
    queue_files = {
        "Twitter_Queue.md": "Twitter/X",
        "Facebook_Queue.md": "Facebook",
        "Instagram_Queue.md": "Instagram",
    }
    
    all_valid = True
    for filename, platform in queue_files.items():
        file_path = social_queue / filename
        if not file_path.exists():
            print(f"  ✗ {platform} ({filename}) - MISSING")
            all_valid = False
            continue
        
        content = file_path.read_text()
        # Check for basic structure
        if "###" in content and "- status:" in content:
            print(f"  ✓ {platform} ({filename}) - valid format")
        else:
            print(f"  ⚠ {platform} ({filename}) - may have invalid format")
            all_valid = False
    
    # Check LinkedIn queue in Plans folder
    linkedin_queue = vault / "Plans" / "LinkedIn_Queue.md"
    if linkedin_queue.exists():
        content = linkedin_queue.read_text()
        if "## Post:" in content and "- status:" in content:
            print(f"  ✓ LinkedIn (LinkedIn_Queue.md) - valid format")
        else:
            print(f"  ⚠ LinkedIn (LinkedIn_Queue.md) - may have invalid format")
            all_valid = False
    else:
        print(f"  ✗ LinkedIn (LinkedIn_Queue.md) - MISSING")
        all_valid = False
    
    return all_valid


def test_watcher_scripts() -> bool:
    """Test 7: Verify all watcher scripts exist."""
    print("\n" + "="*60)
    print("TEST 7: Watcher Scripts")
    print("="*60)
    
    watchers_dir = Path(__file__).parent / "watchers"
    required_watchers = [
        "gmail_watcher.py",
        "filesystem_watcher.py",
        "linkedin_watcher.py",
        "twitter_watcher.py",
        "facebook_watcher.py",
        "orchestrator.py",
    ]
    
    all_exist = True
    for watcher in required_watchers:
        watcher_path = watchers_dir / watcher
        if watcher_path.exists():
            print(f"  ✓ {watcher}")
        else:
            print(f"  ✗ {watcher} - MISSING")
            all_exist = False
    
    return all_exist


def test_whatsapp_baileys() -> bool:
    """Test 8: Check WhatsApp Baileys service configuration."""
    print("\n" + "="*60)
    print("TEST 8: WhatsApp Baileys Service")
    print("="*60)
    
    whatsapp_dir = Path(__file__).parent / "whatsapp-baileys"
    
    if not whatsapp_dir.exists():
        print("  ✗ whatsapp-baileys/ - MISSING")
        return False
    
    index_js = whatsapp_dir / "index.js"
    if not index_js.exists():
        print("  ✗ index.js - MISSING")
        return False
    
    print("  ✓ WhatsApp Baileys directory exists")
    
    # Check auth_info folder
    auth_dir = whatsapp_dir / "auth_info"
    if auth_dir.exists():
        print("  ✓ Auth info folder exists (WhatsApp paired)")
    else:
        print("  ⚠ Auth info folder missing (WhatsApp not paired yet)")
        print("  → Run: node whatsapp-baileys/index.js and scan QR code")
    
    return True


def create_test_action_file(vault: Path) -> Path:
    """Test 9: Create a test action file to verify orchestrator."""
    print("\n" + "="*60)
    print("TEST 9: Create Test Action File")
    print("="*60)
    
    needs_action = vault / "Needs_Action"
    needs_action.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    test_file = needs_action / f"TEST_MANUAL_{timestamp}.md"
    
    content = f"""---
type: manual_test
created: {datetime.utcnow().isoformat()}Z
priority: normal
status: pending
---

## Manual Test File

This is a test file created by test_watchers.py to verify the orchestrator is working.

## Suggested Actions

- [ ] Verify this file appears in Needs_Action
- [ ] Verify the orchestrator processes this file
- [ ] Verify the AI agent creates a response in Pending_Approval or moves to Done
- [ ] Delete this file after testing

## Test Instructions

If you're reading this, the file creation worked. The next step is to verify
the orchestrator picks it up and processes it.
"""
    
    test_file.write_text(content, encoding="utf-8")
    print(f"  ✓ Test file created: {test_file.name}")
    print(f"  → Path: {test_file}")
    print(f"  → Watch the orchestrator logs to see if it's processed")
    
    return test_file


def check_logs(vault: Path) -> bool:
    """Test 10: Check log files for recent activity."""
    print("\n" + "="*60)
    print("TEST 10: Log Files")
    print("="*60)
    
    logs_dir = vault / "Logs"
    if not logs_dir.exists():
        print("  ✗ Logs directory - MISSING")
        return False
    
    # Get today's log file
    today = datetime.utcnow().strftime("%Y-%m-%d")
    log_file = logs_dir / f"{today}.jsonl"
    
    if not log_file.exists():
        print(f"  ⚠ No log file for today ({today})")
        print("  → This might mean watchers haven't logged activity today")
        return False
    
    print(f"  ✓ Log file exists: {log_file.name}")
    
    # Count recent events
    try:
        content = log_file.read_text(encoding="utf-8").strip()
        if content:
            lines = content.splitlines()
            print(f"  ✓ Events logged today: {len(lines)}")
            
            # Show last 3 events
            if len(lines) >= 3:
                print("  Recent events:")
                for line in lines[-3:]:
                    try:
                        event = json.loads(line)
                        action = event.get("action_type", event.get("event", "unknown"))
                        print(f"    - {action}")
                    except:
                        pass
        else:
            print("  ⚠ Log file is empty")
    except Exception as e:
        print(f"  ⚠ Error reading log: {e}")
    
    return True


def run_all_tests(vault: Path, create_test_file: bool = False):
    """Run all tests and generate a report."""
    print("\n" + "="*70)
    print("  AI EMPLOYEE DIGITAL FTE - COMPREHENSIVE SYSTEM TEST")
    print("="*70)
    print(f"\nVault Path: {vault}")
    print(f"Timestamp:  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {}
    
    # Run all tests
    results["vault_structure"] = test_vault_structure(vault)
    results["required_files"] = test_required_files(vault)
    results["env_config"] = test_env_configuration()
    results["needs_action"] = test_needs_action_folder(vault)
    results["pending_approval"] = test_pending_approval_folder(vault)
    results["social_queue"] = test_social_queue_files(vault)
    results["watcher_scripts"] = test_watcher_scripts()
    results["whatsapp"] = test_whatsapp_baileys()
    results["logs"] = check_logs(vault)
    
    if create_test_file:
        test_file = create_test_action_file(vault)
        results["test_file_created"] = test_file.exists()
    
    # Summary
    print("\n" + "="*70)
    print("  TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for v in results.values() if v is True)
    total = len([v for v in results.values() if isinstance(v, bool)])
    
    print(f"\nPassed: {passed}/{total}")
    
    if passed == total:
        print("\n✓ ALL TESTS PASSED - System is ready!")
        print("\nNext Steps:")
        print("  1. Run: start.bat to start all watchers")
        print("  2. Monitor the orchestrator window for activity")
        print("  3. Drop a test file in Inbox/ or send a WhatsApp message")
    else:
        print("\n⚠ SOME TESTS FAILED - Review the issues above")
        print("\nCommon Fixes:")
        print("  - Copy .env.example to .env and fill in credentials")
        print("  - Run Gmail OAuth: python watchers/gmail_watcher.py --get-token")
        print("  - Pair WhatsApp: node whatsapp-baileys/index.js")
        print("  - Ensure all required folders exist in AI_Employee_Vault/")
    
    return results


def main():
    parser = argparse.ArgumentParser(description="AI Employee - System Test Suite")
    parser.add_argument(
        "--vault",
        default=str(Path(__file__).parent / "AI_Employee_Vault"),
        help="Path to your Obsidian vault",
    )
    parser.add_argument(
        "--create-test-file",
        action="store_true",
        help="Create a test action file in Needs_Action",
    )
    args = parser.parse_args()
    
    vault = Path(args.vault).resolve()
    if not vault.exists():
        print(f"ERROR: Vault not found at: {vault}")
        sys.exit(1)
    
    results = run_all_tests(vault, create_test_file=args.create_test_file)
    
    # Exit with error code if critical tests failed
    if not results.get("vault_structure") or not results.get("watcher_scripts"):
        sys.exit(1)
    
    sys.exit(0)


if __name__ == "__main__":
    main()
