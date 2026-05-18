"""
cli.py — Terminal runner for the agent team
Usage:
    python cli.py "Build a real-time collaborative code editor with AI suggestions"
    python cli.py --model qwen3.5:27b "Your project description here"
"""

import argparse
import sys
import textwrap
from agents import run_team, AGENTS, Message

# ──────────────────────────────────────────────
# ANSI colors
# ──────────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"

AGENT_COLORS = {
    "lead":    "\033[35m",   # magenta
    "pm":      "\033[31m",   # red
    "backend": "\033[32m",   # green
    "frontend":"\033[34m",   # blue
    "ai":      "\033[33m",   # yellow → pink-ish
    "devops":  "\033[36m",   # cyan
}

TYPE_PREFIX = {
    "announcement": "📢",
    "update":       "✅",
    "collab":       "🔗",
    "summary":      "🏁",
    "error":        "❌",
}


def fmt_agent(agent_id: str) -> str:
    color = AGENT_COLORS.get(agent_id, "")
    ag = AGENTS.get(agent_id, {})
    name = ag.get("name", agent_id)
    return f"{color}{BOLD}{name}{RESET}"


def print_message(msg: Message):
    prefix   = TYPE_PREFIX.get(msg.msg_type, "  ")
    from_str = fmt_agent(msg.from_id)

    if msg.to_id == "all":
        to_str = f"{DIM}→ All{RESET}"
    else:
        to_str = f"{DIM}→{RESET} {fmt_agent(msg.to_id)}"

    header = f"{prefix}  {from_str}  {to_str}"
    body   = textwrap.fill(msg.content, width=90, initial_indent="     ", subsequent_indent="     ")

    print(header)
    print(body)
    print()


def print_banner(project: str):
    line = "─" * 60
    print(f"\n{BOLD}{line}{RESET}")
    print(f"{BOLD}  Agent Team — On-Premise (Ollama){RESET}")
    print(f"{DIM}  Project: {project[:70]}{RESET}")
    print(f"{BOLD}{line}{RESET}\n")


def print_section(title: str):
    print(f"\n{DIM}{'─'*40}{RESET}")
    print(f"  {BOLD}{title}{RESET}")
    print(f"{DIM}{'─'*40}{RESET}\n")


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Run the AI agent team locally via Ollama")
    parser.add_argument("project", help="Startup project description")
    parser.add_argument("--model", default="qwen3:30b-instruct", help="Ollama model name (default: qwen3:30b-instruct)")
    args = parser.parse_args()

    print_banner(args.project)

    section_shown = {"planning": False, "working": False, "done": False}

    def on_message(msg: Message):
        # Print section headers at the right moments
        if msg.msg_type == "announcement" and not section_shown["planning"]:
            print_section("Phase 1 · Team Lead plans")
            section_shown["planning"] = True

        if msg.msg_type == "update" and not section_shown["working"]:
            print_section("Phase 2 · Team works")
            section_shown["working"] = True

        if msg.msg_type == "summary" and not section_shown["done"]:
            print_section("Phase 3 · Wrap-up")
            section_shown["done"] = True

        print_message(msg)

    try:
        run_team(args.project, model=args.model, on_message=on_message)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌  Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
