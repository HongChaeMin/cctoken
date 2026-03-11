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
from cctoken.config import load_config, save_budget
from cctoken.display import show_summary, show_projects, show_trend, show_budget


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


def main():
    parser = argparse.ArgumentParser(
        prog="cctoken",
        description="Claude Code token usage monitor",
    )
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("projects", help="Per-project breakdown (month-to-date)")
    sub.add_parser("trend", help="Hourly usage heatmap (last 7 days)")

    budget_p = sub.add_parser("budget", help="Manage monthly token budget")
    budget_sub = budget_p.add_subparsers(dest="budget_cmd")
    set_p = budget_sub.add_parser("set", help="Set monthly token budget")
    set_p.add_argument("tokens", help="Token budget (e.g. 5000000)")
    budget_sub.add_parser("show", help="Show budget and current usage")

    args = parser.parse_args()

    if args.cmd is None:
        cmd_summary(args)
    elif args.cmd == "projects":
        cmd_projects(args)
    elif args.cmd == "trend":
        cmd_trend(args)
    elif args.cmd == "budget":
        if args.budget_cmd is None:
            budget_p.print_help()
        else:
            cmd_budget(args)


if __name__ == "__main__":
    main()
