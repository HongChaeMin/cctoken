from __future__ import annotations
import time
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich.layout import Layout
from rich.live import Live
from rich.align import Align
from rich import box

from cctoken.parser import (
    TokenRecord, filter_today, filter_this_week,
    filter_this_month, filter_last_7_days, group_by_project
)
from cctoken.pricing import calculate_cost, format_cost, UNKNOWN_COST
from cctoken.config import Config

console = Console()


def _sum_tokens(records: list[TokenRecord]) -> tuple[int, int]:
    """Returns (display_tokens, cache_tokens)."""
    return (
        sum(r.display_tokens for r in records),
        sum(r.cache_tokens for r in records),
    )


def _sum_cost(records: list[TokenRecord]) -> tuple[float, bool]:
    """Returns (total_known_cost, has_unknown_model)."""
    total = 0.0
    has_unknown = False
    for r in records:
        c = calculate_cost(
            r.model, r.input_tokens, r.cache_creation_tokens,
            r.cache_read_tokens, r.output_tokens
        )
        if c is UNKNOWN_COST:
            has_unknown = True
        else:
            total += c
    return (total, has_unknown)


def _stat_panel(label: str, tokens: int, cost: float, has_unknown: bool) -> Panel:
    # If any record had an unknown model, show ~$?.?? (can't give a reliable estimate)
    cost_str = "~$?.??" if has_unknown else format_cost(cost)
    content = Text()
    content.append(f"{tokens:,}", style="bold cyan")
    content.append(" tokens\n")
    content.append(cost_str, style="bold green")
    return Panel(content, title=f"[bold]{label}[/bold]", border_style="dim")


def _budget_panel(used_tokens: int, budget: int) -> Panel:
    pct = used_tokens / budget
    bar_width = 40
    filled = int(bar_width * min(pct, 1.0))
    remaining = bar_width - filled

    if pct < 0.70:
        color = "green"
        icon = ""
    elif pct < 0.90:
        color = "yellow"
        icon = " ⚠"
    else:
        color = "red"
        icon = " 🚨"

    bar = Text()
    bar.append("█" * filled, style=color)
    bar.append("░" * remaining, style="dim")

    content = Text()
    content.append(f"Budget: {budget:,} tokens/month\n\n")
    content.append(bar)
    content.append(f"\n{pct*100:.1f}% used — {used_tokens:,} / {budget:,}{icon}", style=color)

    return Panel(content, title="[bold]Monthly Budget[/bold]", border_style=color)


def show_summary(records: list[TokenRecord], config: Config) -> None:
    console.print()
    console.rule("[bold magenta]Claude Code Token Usage[/bold magenta]")
    console.print()

    today_r = filter_today(records)
    week_r = filter_this_week(records)
    month_r = filter_this_month(records)

    panels = []
    for label, recs in [("Today", today_r), ("This Week", week_r), ("This Month", month_r)]:
        tokens, _ = _sum_tokens(recs)
        cost, has_unknown = _sum_cost(recs)
        panels.append(_stat_panel(label, tokens, cost, has_unknown))

    console.print(Columns(panels, equal=True))

    if config.monthly_token_budget is not None:
        month_tokens, _ = _sum_tokens(month_r)
        console.print()
        console.print(_budget_panel(month_tokens, config.monthly_token_budget))
    else:
        console.print()
        console.print("[dim]Tip: Run [bold]cctoken budget set <tokens>[/bold] to enable budget tracking[/dim]")

    console.print()


def show_projects(records: list[TokenRecord]) -> None:
    month_records = filter_this_month(records)
    groups = group_by_project(month_records)

    table = Table(title="Projects (month-to-date)", box=box.ROUNDED, border_style="dim")
    table.add_column("Project", style="magenta", no_wrap=True)
    table.add_column("Tokens", style="cyan", justify="right")
    table.add_column("Cached", style="blue", justify="right")
    table.add_column("Cost", style="green", justify="right")
    table.add_column("Sessions", style="white", justify="right")

    rows = []
    for proj, recs in groups.items():
        tokens, cache = _sum_tokens(recs)
        cost, has_unknown = _sum_cost(recs)
        sessions = len({r.session_id for r in recs})
        cost_str = "~$?.??" if has_unknown else format_cost(cost)
        rows.append((proj, tokens, cache, cost_str, sessions))

    for proj, tokens, cache, cost_str, sessions in sorted(rows, key=lambda x: -x[1]):
        table.add_row(proj, f"{tokens:,}", f"{cache:,}", cost_str, str(sessions))

    console.print()
    console.print(table)
    console.print()


def show_trend(records: list[TokenRecord]) -> None:
    week_records = filter_last_7_days(records)

    hourly: dict[int, int] = {h: 0 for h in range(24)}
    for r in week_records:
        hour = r.timestamp.astimezone().hour
        hourly[hour] += r.display_tokens

    max_tokens = max(hourly.values()) or 1
    bar_height = 10

    console.print()
    console.rule("[bold blue]Total tokens by hour of day (last 7 days)[/bold blue]")
    console.print()

    peak_hour = max(hourly, key=lambda h: hourly[h])

    for row in range(bar_height, 0, -1):
        line = Text()
        for hour in range(24):
            val = hourly[hour]
            filled = int((val / max_tokens) * bar_height)
            if filled >= row:
                color = "magenta" if hour == peak_hour else "blue"
                line.append("█ ", style=color)
            else:
                line.append("  ")
        console.print(line)

    label_line = Text()
    for hour in range(24):
        label_line.append(f"{hour:02d}", style="dim")
        label_line.append(" ")
    console.print(label_line)

    console.print(
        f"\n[dim]Peak hour: [bold magenta]{peak_hour:02d}:00[/bold magenta]"
        f" — {hourly[peak_hour]:,} tokens[/dim]"
    )
    console.print()


def show_budget(records: list[TokenRecord], config: Config) -> None:
    if config.monthly_token_budget is None:
        console.print("[yellow]No budget configured. Run: [bold]cctoken budget set <tokens>[/bold][/yellow]")
        return

    month_records = filter_this_month(records)
    used, _ = _sum_tokens(month_records)
    console.print()
    console.print(_budget_panel(used, config.monthly_token_budget))
    console.print()


def _build_watch_renderable(records: list[TokenRecord], config: Config, refresh_count: int):
    """Build the full watch display as a single renderable."""
    from rich.console import Group as RGroup

    now = datetime.now().astimezone()

    today_r = filter_today(records)
    week_r = filter_this_week(records)
    month_r = filter_this_month(records)

    # ── Top header ──────────────────────────────────────────────────────────
    header = Text(justify="center")
    header.append(" ◆ ", style="bold magenta")
    header.append("Claude Code Token Monitor", style="bold white")
    header.append(" ◆ ", style="bold magenta")
    header_panel = Panel(
        Align.center(header),
        border_style="bright_magenta",
        padding=(0, 2),
    )

    # ── Stat columns ────────────────────────────────────────────────────────
    stat_panels = []
    for label, recs in [("Today", today_r), ("This Week", week_r), ("This Month", month_r)]:
        tokens, cache = _sum_tokens(recs)
        cost, has_unknown = _sum_cost(recs)
        cost_str = "~$?.??" if has_unknown else format_cost(cost)

        content = Text(justify="center")
        content.append(f"{tokens:,}\n", style="bold cyan")
        content.append("tokens\n", style="dim")
        content.append(f"{cache:,}\n", style="blue")
        content.append("cached\n", style="dim")
        content.append(cost_str, style="bold green")
        stat_panels.append(Panel(
            Align.center(content),
            title=f"[bold]{label}[/bold]",
            border_style="cyan",
            padding=(0, 1),
        ))

    # ── Projects table ───────────────────────────────────────────────────────
    groups = group_by_project(month_r)
    proj_table = Table(box=box.SIMPLE, border_style="dim", padding=(0, 1))
    proj_table.add_column("Project", style="magenta")
    proj_table.add_column("Tokens", style="cyan", justify="right")
    proj_table.add_column("Cached", style="blue", justify="right")
    proj_table.add_column("Cost", style="green", justify="right")

    rows = []
    for proj, recs in groups.items():
        tokens, cache = _sum_tokens(recs)
        cost, has_unknown = _sum_cost(recs)
        cost_str = "~$?.??" if has_unknown else format_cost(cost)
        rows.append((proj, tokens, cache, cost_str))

    for proj, tokens, cache, cost_str in sorted(rows, key=lambda x: -x[1])[:8]:
        proj_table.add_row(proj, f"{tokens:,}", f"{cache:,}", cost_str)

    proj_panel = Panel(
        proj_table,
        title="[bold]Projects (month-to-date)[/bold]",
        border_style="dim",
    )

    # ── Budget / status bar ──────────────────────────────────────────────────
    if config.monthly_token_budget is not None:
        used, _ = _sum_tokens(month_r)
        budget = config.monthly_token_budget
        pct = min(used / budget, 1.0)
        bar_width = 50
        filled = int(bar_width * pct)

        if pct < 0.70:
            color, icon = "green", "●"
        elif pct < 0.90:
            color, icon = "yellow", "⚠"
        else:
            color, icon = "red", "🚨"

        status = Text()
        status.append(f" {icon} ", style=color)
        status.append("▓" * filled, style=color)
        status.append("░" * (bar_width - filled), style="dim")
        status.append(f"  {pct*100:.1f}%  ", style=f"bold {color}")
        status.append(f"{used:,} / {budget:,} tokens", style="dim")
        status.append(f"  •  refreshed {now.strftime('%H:%M:%S')}", style="dim")
        status_panel = Panel(status, border_style=color, padding=(0, 0))
    else:
        status = Text(justify="center")
        status.append("No budget set  •  ", style="dim")
        status.append("cctoken budget set <tokens>", style="bold dim")
        status.append(f"  •  refreshed {now.strftime('%H:%M:%S')}", style="dim")
        status_panel = Panel(status, border_style="dim", padding=(0, 0))

    return RGroup(
        header_panel,
        Columns(stat_panels, equal=True),
        proj_panel,
        status_panel,
    )


def show_watch(interval: int = 5) -> None:
    """Live-refresh dashboard. Ctrl+C to exit."""
    from cctoken.parser import load_all_records
    from cctoken.config import load_config

    with Live(console=console, refresh_per_second=1, screen=True) as live:
        refresh_count = 0
        next_refresh = 0.0
        while True:
            now = time.monotonic()
            if now >= next_refresh:
                records = load_all_records()
                config = load_config()
                live.update(_build_watch_renderable(records, config, refresh_count))
                refresh_count += 1
                next_refresh = now + interval
            time.sleep(0.2)
