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
    TokenRecord, filter_this_hour, filter_today, filter_this_week,
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


# Sparkline block characters (9 levels)
_SPARKS = " ▁▂▃▄▅▆▇█"


def _sparkline(values: list[int], width: int = 16, color_high: str = "magenta") -> Text:
    """Render a sparkline from a list of values using block chars."""
    if not values:
        return Text("─" * width, style="dim")

    # Pad or truncate to width
    if len(values) < width:
        values = [0] * (width - len(values)) + values
    elif len(values) > width:
        values = values[-width:]

    max_val = max(values) or 1
    t = Text()
    for v in values:
        idx = int(v / max_val * 8)
        char = _SPARKS[idx]
        if idx == 0:
            t.append(char or " ", style="dim")
        elif idx < 3:
            t.append(char, style="cyan")
        elif idx < 6:
            t.append(char, style="bright_cyan")
        else:
            t.append(char, style=f"bold {color_high}")
    return t


def _hour_spark(records: list[TokenRecord]) -> tuple[list[int], list[str]]:
    """Returns (values, labels) for 5-min buckets of current hour."""
    now = datetime.now().astimezone()
    buckets = [0] * 12
    for r in records:
        local = r.timestamp.astimezone()
        if local.date() == now.date() and local.hour == now.hour:
            bucket = local.minute // 5
            buckets[bucket] += r.display_tokens
    labels = [f"{now.hour:02d}:{m*5:02d}" for m in range(12)]
    return buckets, labels


def _today_spark(records: list[TokenRecord]) -> list[int]:
    """Returns hourly token counts (24 values) for today."""
    now = datetime.now().astimezone()
    hourly = [0] * 24
    for r in records:
        local = r.timestamp.astimezone()
        if local.date() == now.date():
            hourly[local.hour] += r.display_tokens
    return hourly


def _week_spark(records: list[TokenRecord]) -> tuple[list[int], list[str]]:
    """Returns (values, day-labels) for Mon–Sun of current week."""
    now = datetime.now().astimezone()
    from datetime import timedelta
    week_start = (now - timedelta(days=now.weekday())).date()
    days = [(week_start + timedelta(days=i)) for i in range(7)]
    daily: dict = {d: 0 for d in days}
    for r in records:
        d = r.timestamp.astimezone().date()
        if d in daily:
            daily[d] += r.display_tokens
    labels = ["M", "T", "W", "T", "F", "S", "S"]
    return [daily[d] for d in days], labels


def _month_spark(records: list[TokenRecord]) -> tuple[list[int], list[str]]:
    """Returns (values, week-labels) split into 4-week buckets for this month."""
    now = datetime.now().astimezone()
    month_start = now.replace(day=1).date()
    # Group by week-of-month (0..3+)
    buckets = [0] * 5
    labels = ["W1", "W2", "W3", "W4", "W5"]
    for r in records:
        d = r.timestamp.astimezone().date()
        if d >= month_start and d.month == now.month:
            week_idx = min((d.day - 1) // 7, 4)
            buckets[week_idx] += r.display_tokens
    return buckets, labels


def _stat_card(
    title: str,
    tokens: int,
    cost: float,
    has_unknown: bool,
    spark_values: list[int],
    spark_labels: list[str] | None = None,
    border: str = "cyan",
) -> Panel:
    """A stat card with sparkline graph."""
    cost_str = "~$?.??" if has_unknown else format_cost(cost)

    content = Text(justify="center")
    content.append(f"{tokens:,}", style="bold cyan")
    content.append(" tok\n", style="dim")

    # Sparkline row
    spark = _sparkline(spark_values, width=len(spark_values), color_high="magenta")
    spark_centered = Align.center(spark)

    # Label row (optional, short)
    if spark_labels and len(spark_labels) <= 12:
        lbl = Text(justify="center")
        for i, l in enumerate(spark_labels):
            lbl.append(l, style="dim")
            if i < len(spark_labels) - 1:
                lbl.append(" ", style="dim")
        label_row = Align.center(lbl)
    else:
        label_row = None

    cost_text = Text(justify="center")
    cost_text.append(cost_str, style="bold green")

    from rich.console import Group as RGroup
    parts = [content, spark_centered]
    if label_row:
        parts.append(label_row)
    parts.append(cost_text)

    return Panel(
        Align.center(RGroup(*parts)),
        title=f"[bold]{title}[/bold]",
        border_style=border,
        padding=(0, 1),
    )


def _project_bars(records: list[TokenRecord]) -> Panel:
    """Project leaderboard with inline horizontal token bars."""
    groups = group_by_project(records)
    rows = []
    for proj, recs in groups.items():
        tokens, _ = _sum_tokens(recs)
        cost, has_unknown = _sum_cost(recs)
        cost_str = "~$?.??" if has_unknown else format_cost(cost)
        rows.append((proj, tokens, cost_str))

    rows.sort(key=lambda x: -x[1])
    rows = rows[:7]
    if not rows:
        return Panel(Text("No data this month", style="dim"), title="[bold]Projects[/bold]", border_style="dim")

    max_tok = rows[0][1] or 1
    bar_width = 24

    content = Text()
    for i, (proj, tokens, cost_str) in enumerate(rows):
        filled = int(tokens / max_tok * bar_width)
        empty = bar_width - filled

        # Rank color
        rank_colors = ["bold yellow", "bold white", "dim white"] + ["dim"] * 10
        rank_style = rank_colors[i]

        content.append(f"  {proj:<22}", style="magenta")
        content.append(" ")
        content.append("█" * filled, style="cyan")
        content.append("░" * empty, style="dim")
        content.append(f"  {tokens:>8,}", style="bold cyan")
        content.append(f"  {cost_str}", style="green")
        if i < len(rows) - 1:
            content.append("\n")

    return Panel(
        content,
        title="[bold]Projects[/bold] [dim](month-to-date)[/dim]",
        border_style="dim",
    )


def _status_bar(records: list[TokenRecord], config: Config, now: datetime) -> Text:
    """Claude Code-style bottom status bar — single line, no wrapping."""
    month_r = filter_this_month(records)
    used, _ = _sum_tokens(month_r)
    cost_total, _ = _sum_cost(month_r)
    cost_str = format_cost(cost_total)

    bar = Text(no_wrap=True, overflow="ellipsis")

    if config.monthly_token_budget is not None:
        budget = config.monthly_token_budget
        pct = min(used / budget, 1.0)
        bar_width = 28
        filled = int(bar_width * pct)
        color = "green" if pct < 0.70 else ("yellow" if pct < 0.90 else "red")

        bar.append(" ▐", style="dim")
        bar.append("█" * filled, style=color)
        bar.append("░" * (bar_width - filled), style="dim")
        bar.append("▌", style="dim")
        bar.append(f" {pct*100:.1f}%", style=f"bold {color}")
        bar.append(f"  {used:,} / {budget:,} tok", style="dim")
    else:
        bar.append(f"  ◈ {used:,} tok this month", style="cyan")

    bar.append("   ·   ", style="dim")
    bar.append(cost_str, style="green")
    bar.append(" est.", style="dim")
    bar.append("   ·   ", style="dim")
    bar.append(f"⟳ {now.strftime('%H:%M:%S')}", style="dim")
    bar.append("   ·   ", style="dim")
    bar.append("Ctrl+C to exit", style="dim")
    return bar


def _build_watch_renderable(records: list[TokenRecord], config: Config):
    """Build the full watch display."""
    from rich.console import Group as RGroup

    now = datetime.now().astimezone()

    hour_r = filter_this_hour(records)
    today_r = filter_today(records)
    week_r = filter_this_week(records)
    month_r = filter_this_month(records)

    # ── Header ──────────────────────────────────────────────────────────────
    ts = now.strftime("%Y-%m-%d  %H:%M:%S")
    header = Text(justify="center")
    header.append("◆ ", style="bright_magenta")
    header.append("Claude Code Token Monitor", style="bold white")
    header.append("  ◆  ", style="dim")
    header.append(ts, style="dim")
    header_panel = Panel(Align.center(header), border_style="bright_magenta", padding=(0, 0))

    # ── Stat cards ──────────────────────────────────────────────────────────
    hour_vals, _ = _hour_spark(records)
    today_vals = _today_spark(records)
    week_vals, week_lbls = _week_spark(records)
    month_vals, month_lbls = _month_spark(records)

    def card(title, recs, spark_vals, spark_lbls, border="cyan"):
        tokens, _ = _sum_tokens(recs)
        cost, has_unknown = _sum_cost(recs)
        return _stat_card(title, tokens, cost, has_unknown, spark_vals, spark_lbls, border)

    stat_panels = [
        card("Hour",       hour_r,  hour_vals,  None,       border="bright_cyan"),
        card("Today",      today_r, today_vals, None,       border="cyan"),
        card("This Week",  week_r,  week_vals,  week_lbls,  border="blue"),
        card("This Month", month_r, month_vals, month_lbls, border="magenta"),
    ]

    # ── Projects ─────────────────────────────────────────────────────────────
    proj_panel = _project_bars(month_r)

    # ── Status bar ───────────────────────────────────────────────────────────
    status = _status_bar(records, config, now)
    status_panel = Panel(status, border_style="dim", padding=(0, 0))

    return RGroup(
        header_panel,
        Columns(stat_panels, equal=True, expand=True),
        proj_panel,
        status_panel,
    )


def show_watch(interval: int = 5) -> None:
    """Live-refresh dashboard. Ctrl+C to exit."""
    from cctoken.parser import load_all_records, filter_this_hour
    from cctoken.config import load_config

    with Live(console=console, refresh_per_second=1, screen=True) as live:
        next_refresh = 0.0
        while True:
            now = time.monotonic()
            if now >= next_refresh:
                records = load_all_records()
                config = load_config()
                live.update(_build_watch_renderable(records, config))
                next_refresh = now + interval
            time.sleep(0.2)
