#!/usr/bin/env python3
"""cctoken — Claude Code token usage monitor."""

import argparse
import sys
from pathlib import Path

# Ensure the project root is on sys.path when run as a script/symlink
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from cctoken.parser import load_all_records
from cctoken.config import load_config, save_budget, save_reset_day
from cctoken.display import show_summary, show_projects, show_trend, show_budget, show_watch


def cmd_summary(_args):
    records = load_all_records()
    config = load_config()
    show_summary(records, config)


def cmd_projects(_args):
    records = load_all_records()
    show_projects(records)


def cmd_trend(_args):
    records = load_all_records()
    show_trend(records)


def cmd_watch(_args):
    try:
        show_watch(interval=5)
    except KeyboardInterrupt:
        pass


def cmd_budget(args):
    if args.budget_cmd == "set":
        try:
            tokens = int(args.tokens)
        except (ValueError, TypeError):
            print(f"Error: '{args.tokens}' is not a valid number.", file=sys.stderr)
            sys.exit(1)
        save_budget(tokens)
        print(f"Budget set to {tokens:,} tokens/month")
    elif args.budget_cmd == "show":
        records = load_all_records()
        config = load_config()
        show_budget(records, config)
    elif args.budget_cmd == "reset-day":
        try:
            day = int(args.day)
            if not 1 <= day <= 28:
                raise ValueError
        except (ValueError, TypeError):
            print("Error: day must be 1–28.", file=sys.stderr)
            sys.exit(1)
        save_reset_day(day)
        print(f"Billing reset day set to {day} (every month on the {day}th)")


def main():
    parser = argparse.ArgumentParser(
        prog="cctoken",
        description="Claude Code token usage monitor",
    )
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("projects", help="Per-project breakdown (month-to-date)")
    sub.add_parser("trend", help="Hourly usage heatmap (last 7 days)")
    sub.add_parser("watch", help="Live dashboard, refreshes every 5s (Ctrl+C to exit)")

    budget_p = sub.add_parser("budget", help="Manage monthly token budget")
    budget_sub = budget_p.add_subparsers(dest="budget_cmd")
    set_p = budget_sub.add_parser("set", help="Set monthly token budget")
    set_p.add_argument("tokens", help="Token budget (e.g. 5000000)")
    budget_sub.add_parser("show", help="Show budget and current usage")
    reset_p = budget_sub.add_parser("reset-day", help="Set the day of month when tokens reset (1–28)")
    reset_p.add_argument("day", help="Day of month (e.g. 1 for 1st, 15 for 15th)")

    args = parser.parse_args()

    if args.cmd is None:
        cmd_summary(args)
    elif args.cmd == "projects":
        cmd_projects(args)
    elif args.cmd == "trend":
        cmd_trend(args)
    elif args.cmd == "watch":
        cmd_watch(args)
    elif args.cmd == "budget":
        if args.budget_cmd is None:
            budget_p.print_help()
        else:
            cmd_budget(args)


if __name__ == "__main__":
    main()
