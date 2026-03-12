# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

cctoken is a CLI tool that monitors Claude Code token usage by reading JSONL session logs from `~/.claude/projects/**/*.jsonl`. It provides live dashboards, period-specific views, budget tracking, and per-project cost breakdowns using the Rich library.

## Commands

```bash
# Run
cctoken                  # Live watch dashboard (default)
cctoken hour             # Current 5h block detail view
cctoken today            # Today detail view
cctoken week             # This week detail view
cctoken month            # This month detail view

# Test
python3 -m pytest                                              # All tests
python3 -m pytest cctoken/tests/test_parser.py -v              # Single file
python3 -m pytest cctoken/tests/test_parser.py::test_parse_record_basic -v  # Single test

# Install
pip install -r requirements.txt && bash install.sh
```

## Architecture

**Data flow:** JSONL files → `parser.py` (TokenRecord) → `display.py` (Rich UI)

- `parser.py` — `TokenRecord` dataclass, `load_all_records()`, time-based filter functions (`filter_today`, `filter_this_week`, `filter_current_5h_block`, etc.)
- `display.py` — All rendering logic. Two main paths:
  - `show_watch()` → `_build_watch_renderable()` — main live dashboard with 4 stat cards
  - `show_detail_watch()` → `_build_detail_renderable()` — period detail views (hour/today/week/month) with budget bar, model usage, projects, velocity panel
- `pricing.py` — Cost calculation per model (sonnet, opus, haiku). Returns `UNKNOWN_COST` sentinel for unknown models.
- `config.py` — Reads/writes `~/.cctoken.json` for `monthly_token_budget` and `billing_reset_day`.
- `cctoken.py` — CLI entry point with argparse routing.

**Key patterns:**
- Timestamps stored in UTC, converted to local via `.astimezone()` on display
- Full-width responsive bars use `__rich_console__` protocol (`_FullWidthBudgetBar`, `_FullWidthModelBar`, `_Sparkline`, `_Axis`)
- Hour view uses fixed 5-hour blocks (00-05, 05-10, 10-15, 15-20, 20-01), not rolling windows
- Budget is proportionally allocated per period (`_period_budget`): monthly → weekly → daily → 5h block
- All detail views are live-refreshing (5s interval, `screen=True`)

## Dependencies

Python 3.10+, `rich>=13.0.0` (only external dependency).
