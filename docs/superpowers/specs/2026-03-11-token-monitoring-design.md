# Claude Code Token Usage Monitor (cctoken) — Design Spec

**Date:** 2026-03-11
**Status:** Approved

## Overview

A local CLI tool that parses Claude Code's JSONL session logs to show token usage statistics, cost estimates, and budget alerts. Single-machine scope — tracks usage only from the local `~/.claude/projects/` directory.

## Goals

- Track token usage by day / week / month
- Compare usage across projects (`cwd`-based grouping)
- Show time-of-day usage patterns
- Estimate cost using official Anthropic model pricing
- Alert when usage exceeds user-defined token budget

## Non-Goals

- Multi-user / cross-machine aggregation
- Integration with Anthropic billing API (Pro/Max is flat-rate)
- Real-time streaming updates

## Architecture

### File Structure

```
cctoken/
├── cctoken.py        # CLI entry point (argparse subcommands)
├── parser.py         # JSONL parsing and token aggregation
├── pricing.py        # Model pricing table and cost calculation
├── config.py         # Budget config load/save (~/.cctoken.json)
└── display.py        # rich-based terminal output
```

Installed as: `~/.local/bin/cctoken` → symlink to `cctoken/cctoken.py`

### Data Source

`~/.claude/projects/**/*.jsonl` — each file is one session.

Relevant records: `type == "assistant"` entries containing `message.usage`:

```json
{
  "timestamp": "2026-03-11T02:56:15Z",
  "sessionId": "...",
  "cwd": "/Users/.../project-name",
  "message": {
    "model": "claude-sonnet-4-6",
    "usage": {
      "input_tokens": 3,
      "cache_creation_input_tokens": 23732,
      "cache_read_input_tokens": 0,
      "output_tokens": 6
    }
  }
}
```

### Token Counting

Two separate metrics are tracked per record:

- **Display tokens** = `input_tokens + output_tokens` (shown in UI as "tokens used")
- **Cache tokens** = `cache_creation_input_tokens + cache_read_input_tokens` (shown separately as "cached")

Cost is always calculated using all four fields with their respective rates (see Pricing).

Malformed `usage` fields (missing keys or wrong types) are skipped silently; the record is treated as if it has zero tokens.

### Pricing

Estimated cost based on public Anthropic pricing for `claude-sonnet-4-6`:

| Field                          | Rate (per 1M tokens) |
|--------------------------------|----------------------|
| `input_tokens`                 | $3.00                |
| `cache_creation_input_tokens`  | $3.75                |
| `cache_read_input_tokens`      | $0.30                |
| `output_tokens`                | $15.00               |

Pricing stored in `pricing.py` as a dict keyed by model name. If a model name is not in the table, cost is displayed as `~$?.??` (unknown) and the record's tokens are still counted for usage display.

### Budget Config

Stored in `~/.cctoken.json`:

```json
{
  "monthly_token_budget": 5000000
}
```

"Monthly" = calendar month in the user's local timezone.

## Timezone Handling

All timestamp grouping (today, this week, this month) uses the **local machine timezone** (`datetime.now().astimezone()`). JSONL timestamps are UTC ISO 8601 strings and are converted to local time before grouping.

## CLI Interface

```bash
cctoken                     # Default: today / week / month summary
cctoken projects            # Per-project breakdown (month-to-date)
cctoken trend               # Hourly usage heatmap (last 7 rolling days)
cctoken budget set 5000000  # Set monthly token budget
cctoken budget show         # Show current month budget vs usage
```

## Output Design

### Default View (`cctoken`)

Three-column summary panel:
- **Today** / **This Week** / **This Month** — each shows display tokens (cyan) + estimated cost (green)
- Monthly budget progress bar (if configured):
  - Green `█` < 70%
  - Yellow `█` + ⚠ warning at 70–90%
  - Red `█` + 🚨 alert above 90%

### Projects View (`cctoken projects`)

Month-to-date rich table. Columns: **Project** (magenta, last 2 path segments), **Tokens** (cyan), **Cached** (blue), **Cost** (green), **Sessions** (white). Sorted by token count descending.

**Project name:** derived from `cwd` as the last 2 path segments (e.g. `/Users/foo/Company/my-project` → `Company/my-project`). If `cwd` has only 1 segment, show it as-is.

### Trend View (`cctoken trend`)

24-hour bar chart using rich. Data source: last 7 rolling days (168 hours back from now). Each bar = total display tokens for that hour-of-day across the 7-day window. Peak hour bar highlighted in magenta, others in blue.

Label shows: `"Total tokens by hour of day (last 7 days)"` — y-axis is the sum of tokens for that hour across all 7 days (not divided by 7).

### Budget View (`cctoken budget show`)

Reuses the same monthly budget panel from the default view, standalone. "Current usage" = month-to-date display tokens (same scope as default view's Month column).

## Error Handling

| Situation | Behavior |
|-----------|----------|
| `~/.claude/projects/` missing | Print clear message, exit 0 |
| Malformed JSONL line (invalid JSON) | Skip line silently |
| Valid JSON but missing `message.usage` keys | Skip record, treat as 0 tokens |
| Unknown model name | Count tokens, display cost as `~$?.??` |
| No budget configured | Skip budget section, show hint: `Run cctoken budget set <tokens>` |
| `budget set` succeeds | Print: `Budget set to X tokens/month` |
| Valid JSON but missing `message.usage` keys | Treat as 0 tokens (skip contributing to totals) |

## Dependencies

- Python 3.9+
- `rich` (terminal UI)

## Acceptance Criteria

Given a session JSONL with two assistant records:
- Record A: `input=100, cache_creation=500, cache_read=200, output=50`, model=`claude-sonnet-4-6`
- Record B: `input=0, cache_creation=0, cache_read=0, output=0` (empty usage)

Expected:
- Display tokens = (100 + 50) = **150**
- Cache tokens = (500 + 200) = **700**
- Cost = (100×$3 + 500×$3.75 + 200×$0.30 + 50×$15) / 1,000,000 = **$0.002685**
- Record B contributes 0 to all metrics
