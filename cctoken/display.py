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


def _sparkline(values: list[int], color_high: str = "magenta", repeat: int = 1) -> Text:
    """Render a sparkline. Width = len(values) * repeat."""
    max_val = max(values) if values else 0
    t = Text()
    for v in values:
        idx = int(v / max_val * 8) if max_val else 0
        char = _SPARKS[idx] * repeat
        if idx == 0:
            t.append(char or " " * repeat, style="dim")
        elif idx < 3:
            t.append(char, style="cyan")
        elif idx < 6:
            t.append(char, style="bright_cyan")
        else:
            t.append(char, style=f"bold {color_high}")
    return t


# ── Data helpers ──────────────────────────────────────────────────────────────

def _hour_buckets(records: list[TokenRecord]) -> tuple[list[int], str]:
    """12 x 5-min buckets for current hour. Returns (values, range_label)."""
    now = datetime.now().astimezone()
    buckets = [0] * 12
    for r in records:
        local = r.timestamp.astimezone()
        if local.date() == now.date() and local.hour == now.hour:
            buckets[local.minute // 5] += r.display_tokens
    range_lbl = f"{now.hour:02d}:00 – {now.hour:02d}:59"
    return buckets, range_lbl


def _today_buckets(records: list[TokenRecord]) -> tuple[list[int], str]:
    """24 hourly buckets for today. Returns (values, axis_placeholder).
    Axis is built dynamically in _build_watch_renderable using the actual repeat value."""
    now = datetime.now().astimezone()
    hourly = [0] * 24
    for r in records:
        local = r.timestamp.astimezone()
        if local.date() == now.date():
            hourly[local.hour] += r.display_tokens
    return hourly, ""


def _today_axis(repeat: int) -> str:
    """Build Today hour axis with the given char repeat per bucket."""
    width = 24 * repeat
    axis = [" "] * width
    for h, label in [(0, "0"), (6, "6"), (12, "12"), (18, "18"), (23, "23")]:
        idx = h * repeat
        for j, ch in enumerate(label):
            if idx + j < width:
                axis[idx + j] = ch
    return "".join(axis)


def _week_buckets(records: list[TokenRecord]) -> tuple[list[int], str]:
    """7 daily buckets Mon–Sun. Returns (values, axis_str)."""
    from datetime import timedelta
    now = datetime.now().astimezone()
    week_start = (now - timedelta(days=now.weekday())).date()
    days = [week_start + timedelta(days=i) for i in range(7)]
    daily = {d: 0 for d in days}
    for r in records:
        d = r.timestamp.astimezone().date()
        if d in daily:
            daily[d] += r.display_tokens
    # 1 char per day: M T W T F S S
    axis = "M T W T F S S"
    return [daily[d] for d in days], axis


def _month_buckets(records: list[TokenRecord]) -> tuple[list[int], str]:
    """Weekly buckets for this month. Returns (values, axis_str)."""
    now = datetime.now().astimezone()
    month_start = now.replace(day=1).date()
    buckets = [0] * 5
    for r in records:
        d = r.timestamp.astimezone().date()
        if d >= month_start and d.month == now.month:
            buckets[min((d.day - 1) // 7, 4)] += r.display_tokens
    return buckets, "W1W2W3W4W5"


# ── Card builders ─────────────────────────────────────────────────────────────

def _stat_card(
    title: str, emoji: str,
    tokens: int, cost: float, has_unknown: bool,
    spark: Text,
    axis: str | None = None,
    subtitle: str | None = None,
    border: str = "cyan",
) -> Panel:
    from rich.console import Group as RGroup

    cost_str = "~$?.??" if has_unknown else format_cost(cost)

    # Token count line
    tok_line = Text(justify="center")
    tok_line.append(f"{emoji} ", style="bold")
    tok_line.append(f"{tokens:,}", style="bold cyan")
    tok_line.append(" tok", style="dim")

    # Optional subtitle (e.g. time range for Hour)
    parts: list = [tok_line]
    if subtitle:
        sub = Text(subtitle, justify="center", style="dim")
        parts.append(sub)

    # Sparkline (pre-rendered Text)
    parts.append(Align.center(spark))

    # Axis string below sparkline
    if axis:
        parts.append(Align.center(Text(axis, style="dim")))

    # Cost
    cost_line = Text(justify="center")
    cost_line.append(cost_str, style="bold green")
    parts.append(cost_line)

    return Panel(
        Align.center(RGroup(*parts)),
        title=f"[bold]{title}[/bold]",
        border_style=border,
        padding=(0, 1),
    )


# ── Project bars ──────────────────────────────────────────────────────────────

def _project_bars(records: list[TokenRecord], max_rows: int = 6, bar_width: int = 20) -> Panel | None:
    groups = group_by_project(records)
    rows = []
    for proj, recs in groups.items():
        tokens, _ = _sum_tokens(recs)
        cost, has_unknown = _sum_cost(recs)
        rows.append((proj, tokens, "~$?.??" if has_unknown else format_cost(cost)))

    rows.sort(key=lambda x: -x[1])
    rows = rows[:max_rows]
    if not rows:
        return Panel(
            Text("  No sessions recorded this month", style="dim italic"),
            title="[bold]🗂  Projects[/bold] [dim](month-to-date)[/dim]",
            border_style="dim",
        )

    max_tok = rows[0][1] or 1
    medals = ["🥇", "🥈", "🥉"] + ["  "] * 20

    content = Text()
    for i, (proj, tokens, cost_str) in enumerate(rows):
        filled = int(tokens / max_tok * bar_width)
        empty = bar_width - filled
        medal = medals[i]

        content.append(f"  {medal} ", style="")
        content.append(f"{proj:<22}", style="bold magenta" if i == 0 else "magenta")
        content.append("  ")
        content.append("█" * filled, style="bright_cyan" if i == 0 else "cyan")
        content.append("░" * empty, style="dim")
        content.append(f"  {tokens:>9,}", style="bold cyan")
        content.append(f"  {cost_str}", style="green")
        if i < len(rows) - 1:
            content.append("\n")

    return Panel(
        content,
        title="[bold]🗂  Projects[/bold] [dim](month-to-date)[/dim]",
        border_style="dim",
    )


# ── Velocity panel ────────────────────────────────────────────────────────────

def _next_reset(reset_day: int, now: datetime) -> datetime:
    """Return the next billing reset datetime (same time as now, on reset_day)."""
    from datetime import timedelta
    import calendar
    candidate = now.replace(day=reset_day, hour=0, minute=0, second=0, microsecond=0)
    if candidate <= now:
        # roll to next month
        year = now.year + (now.month // 12)
        month = (now.month % 12) + 1
        last_day = calendar.monthrange(year, month)[1]
        candidate = candidate.replace(year=year, month=month, day=min(reset_day, last_day))
    return candidate


def _fmt_duration(seconds: float) -> str:
    seconds = int(seconds)
    d, s = divmod(seconds, 86400)
    h, s = divmod(s, 3600)
    m = s // 60
    if d:
        return f"{d}d {h}h"
    if h:
        return f"{h}h {m}m"
    return f"{m}m"


def _velocity_panel(records: list[TokenRecord], config: Config, now: datetime) -> Panel:
    from rich.console import Group as RGroup
    from datetime import timedelta

    # Burn rate: tokens in the last 24 hours
    cutoff_24h = now - timedelta(hours=24)
    recent = [r for r in records if r.timestamp.astimezone() >= cutoff_24h]
    tokens_24h, _ = _sum_tokens(recent)
    burn_per_hour = tokens_24h / 24

    lines: list = []

    # Burn rate line
    rate_line = Text()
    rate_line.append("🔥 ", style="")
    rate_line.append(f"{burn_per_hour:,.0f}", style="bold yellow")
    rate_line.append(" tok/hr", style="dim")
    rate_line.append("  (last 24h avg)", style="dim")
    lines.append(rate_line)

    # Budget depletion estimate
    if config.monthly_token_budget is not None:
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_r = [r for r in records if r.timestamp.astimezone() >= month_start]
        used, _ = _sum_tokens(month_r)
        remaining = config.monthly_token_budget - used

        dep_line = Text()
        if burn_per_hour > 0 and remaining > 0:
            hours_left = remaining / burn_per_hour
            dep_line.append("📉 ", style="")
            dep_line.append("budget runs out in ", style="dim")
            dep_line.append(_fmt_duration(hours_left * 3600), style="bold red" if hours_left < 24 else "bold cyan")
            dep_line.append(f"  ({remaining:,} tok left)", style="dim")
        elif remaining <= 0:
            dep_line.append("🚨 ", style="")
            dep_line.append("budget exhausted", style="bold red")
        else:
            dep_line.append("📉 ", style="")
            dep_line.append("no recent activity to estimate", style="dim")
        lines.append(dep_line)

    # Reset countdown
    if config.billing_reset_day is not None:
        reset_dt = _next_reset(config.billing_reset_day, now)
        secs_left = (reset_dt - now).total_seconds()
        reset_line = Text()
        reset_line.append("🔄 ", style="")
        reset_line.append("resets in ", style="dim")
        reset_line.append(_fmt_duration(secs_left), style="bold green")
        reset_line.append(f"  ({reset_dt.strftime('%b %d')})", style="dim")
        lines.append(reset_line)
    else:
        hint = Text("💡 run: cctoken budget reset-day <day>  to show reset countdown", style="dim italic")
        lines.append(hint)

    return Panel(
        RGroup(*lines),
        title="[bold]📊 Rate & Reset[/bold]",
        border_style="yellow",
        padding=(0, 1),
    )


# ── Status bar ────────────────────────────────────────────────────────────────

def _status_bar(records: list[TokenRecord], now: datetime) -> Text:
    all_tokens, _ = _sum_tokens(records)

    bar = Text(no_wrap=True, overflow="ellipsis")
    bar.append(f" ⟳ {now.strftime('%H:%M:%S')}", style="dim")
    bar.append("  ·  ", style="dim")
    bar.append(f"📚 {all_tokens:,} tok all-time", style="dim")
    bar.append("  ·  ", style="dim")
    bar.append("Ctrl+C to exit", style="dim")
    return bar


# ── Main renderable ───────────────────────────────────────────────────────────

def _build_watch_renderable(
    records: list[TokenRecord], config: Config,
    term_width: int = 120, term_height: int = 40,
):
    from rich.console import Group as RGroup

    now = datetime.now().astimezone()

    hour_r  = filter_this_hour(records)
    today_r = filter_today(records)
    week_r  = filter_this_week(records)
    month_r = filter_this_month(records)

    # ── Header ────────────────────────────────────────────────────────────────
    header = Text(justify="center")
    header.append("⚡ Claude Code Token Monitor  ", style="bold white")
    header.append(now.strftime("%Y-%m-%d  %H:%M:%S"), style="dim")
    header_panel = Panel(Align.center(header), border_style="bright_magenta", padding=(0, 0))

    # ── Stat cards ────────────────────────────────────────────────────────────
    hour_vals, hour_range  = _hour_buckets(records)
    today_vals, today_axis = _today_buckets(records)
    week_vals, week_lbls   = _week_buckets(records)
    month_vals, month_lbls = _month_buckets(records)

    # Dynamic repeat: fill ~panel inner width for each sparkline
    # panel_inner ≈ (term_width - 4 panels × 3 borders) // 4 - 2 padding
    panel_inner = max(10, (term_width - 16) // 4)

    def repeat_for(buckets: list[int]) -> int:
        return max(1, panel_inner // len(buckets))

    def make_card(title, emoji, recs, spark, axis=None, subtitle=None, border="cyan"):
        tokens, _ = _sum_tokens(recs)
        cost, unk  = _sum_cost(recs)
        spark_text = _sparkline(spark, repeat=repeat_for(spark))
        return _stat_card(title, emoji, tokens, cost, unk, spark_text, axis, subtitle, border)

    stat_panels = [
        make_card("Hour",       "⚡", hour_r,  hour_vals,
                  subtitle=hour_range,  border="bright_cyan"),
        make_card("Today",      "☀️ ", today_r, today_vals,
                  axis=_today_axis(repeat_for(today_vals)), border="cyan"),
        make_card("This Week",  "📅", week_r,  week_vals,
                  axis=week_lbls,       border="blue"),
        make_card("This Month", "📆", month_r, month_vals,
                  axis=month_lbls,      border="magenta"),
    ]

    # ── Projects (adaptive rows based on terminal height) ─────────────────────
    # Fixed overhead: header(3) + stat cards(8) + status bar(3) + project panel borders(2) = 16
    FIXED_LINES = 16
    max_proj_rows = max(0, term_height - FIXED_LINES)
    proj_panel = _project_bars(month_r, max_rows=max_proj_rows) if max_proj_rows > 0 else None

    # ── Status bar ────────────────────────────────────────────────────────────
    status_panel = Panel(
        _status_bar(records, now),
        border_style="dim",
        padding=(0, 0),
    )

    # ── Velocity ───────────────────────────────────────────────────────────────
    velocity_panel = _velocity_panel(records, config, now)

    parts = [header_panel, Columns(stat_panels, equal=True, expand=True), velocity_panel]
    if proj_panel is not None:
        parts.append(proj_panel)
    parts.append(status_panel)
    return RGroup(*parts)


# ── Watch entry point ─────────────────────────────────────────────────────────

def show_watch(interval: int = 5) -> None:
    """Live-refresh dashboard. Ctrl+C to exit."""
    import shutil
    import sys
    from cctoken.parser import load_all_records
    from cctoken.config import load_config

    # Disable mouse tracking so scroll events don't leak as escape sequences
    sys.stdout.write("\x1b[?1000l\x1b[?1002l\x1b[?1003l\x1b[?1006l")
    sys.stdout.flush()

    watch_console = Console()

    with Live(
        console=watch_console,
        refresh_per_second=2,
        screen=True,
        vertical_overflow="crop",
    ) as live:
        next_refresh = 0.0
        while True:
            now = time.monotonic()
            if now >= next_refresh:
                term = shutil.get_terminal_size()
                records = load_all_records()
                config  = load_config()
                live.update(_build_watch_renderable(
                    records, config,
                    term_width=term.columns, term_height=term.lines,
                ))
                next_refresh = now + interval
            time.sleep(0.25)
