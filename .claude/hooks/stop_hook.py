"""
stop_hook.py - Ralph Wiggum Loop (Gold Tier).

Claude Code calls this script when the agent is about to stop.
- If TASK_COMPLETE is found in the transcript → exit 0 (allow stop).
- If max iterations reached              → exit 0 (safety cap, allow stop).
- Otherwise                              → exit 2 (force Claude to keep going).

Claude Code passes transcript data via stdin as JSON.
"""

import json
import sys

MAX_ITERATIONS = 5  # safety cap — never loop more than this many times


def main():
    raw = sys.stdin.read()

    # Check for completion signal anywhere in the raw output
    if "TASK_COMPLETE" in raw:
        sys.exit(0)

    # Count how many assistant turns have happened (loop guard)
    try:
        data = json.loads(raw)
        transcript = data.get("transcript", [])
        assistant_turns = sum(1 for m in transcript if m.get("role") == "assistant")
        if assistant_turns >= MAX_ITERATIONS:
            print(f"[Ralph Wiggum] Max iterations ({MAX_ITERATIONS}) reached. Stopping.", file=sys.stderr)
            sys.exit(0)
    except (json.JSONDecodeError, TypeError):
        # Can't parse transcript — don't loop blindly, allow stop
        sys.exit(0)

    # Task not complete — tell Claude to keep going
    print("Task not complete. Continue working until you can output TASK_COMPLETE.", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
