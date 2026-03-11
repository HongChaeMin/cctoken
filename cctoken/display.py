from __future__ import annotations
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
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
