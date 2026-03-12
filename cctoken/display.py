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
    filter_this_month, filter_last_7_days, filter_current_5h_block,
    current_5h_block, group_by_project,
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


# ── Detail view (hour / today / month) ────────────────────────────────────────

def _group_by_model(records: list[TokenRecord]) -> dict[str, int]:
    models: dict[str, int] = {}
    for r in records:
        models[r.model] = models.get(r.model, 0) + r.display_tokens
    return models


def _period_budget(monthly_budget: int | None, period: str, now: datetime) -> tuple[int | None, str]:
    """Calculate the budget allocation for a given period.
    Returns (budget_tokens, label)."""
    import calendar
    if monthly_budget is None:
        return None, ""
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    if period == "hour":
        blocks = days_in_month * 24 / 5
        return int(monthly_budget / blocks), "5h Budget"
    elif period == "today":
        return int(monthly_budget / days_in_month), "Daily Budget"
    elif period == "week":
        return int(monthly_budget * 7 / days_in_month), "Weekly Budget"
    else:
        return monthly_budget, "Monthly Budget"


class _FullWidthBudgetBar:
    """Full-width budget bar with cost/cache info, rendered at actual panel width."""

    def __init__(self, used: int, budget: int, cost_str: str, cache: int):
        self.used = used
        self.budget = budget
        self.cost_str = cost_str
        self.cache = cache

    def __rich_console__(self, console, options):
        width = options.max_width
        pct = self.used / self.budget if self.budget > 0 else 0
        if pct < 0.70:
            color = "green"
        elif pct < 0.90:
            color = "yellow"
        else:
            color = "red"

        filled = int(width * min(pct, 1.0))
        remaining = width - filled
        bar = Text(no_wrap=True)
        bar.append("█" * filled, style=color)
        bar.append("░" * remaining, style="dim")
        yield bar

        info = Text()
        info.append(f"{self.used:,}", style="bold cyan")
        info.append(f" / {self.budget:,}", style="dim")
        info.append(f"  {pct*100:.1f}%", style=f"bold {color}")
        info.append("  ·  ", style="dim")
        info.append(f"{self.cache:,}", style="bold blue")
        info.append(" cached", style="dim")
        info.append("  ·  ", style="dim")
        info.append(self.cost_str, style="bold green")
        yield info


def _detail_budget_bar(used: int, budget: int | None, label: str, cost_str: str, cache: int) -> Panel:
    if budget is None:
        content = Text()
        content.append("  No budget configured. Run: ", style="dim")
        content.append("cctoken budget set <tokens>", style="bold")
        return Panel(content, title="[bold]Budget[/bold]", border_style="dim")

    pct = used / budget if budget > 0 else 0
    if pct < 0.70:
        color = "green"
    elif pct < 0.90:
        color = "yellow"
    else:
        color = "red"

    return Panel(
        _FullWidthBudgetBar(used, budget, cost_str, cache),
        title=f"[bold]{label}[/bold]",
        border_style=color,
        padding=(0, 1),
    )


def _detail_reset_line(config: Config, now) -> Text:
    line = Text()
    if config.billing_reset_day is not None:
        reset_dt = _next_reset(config.billing_reset_day, now)
        secs_left = (reset_dt - now).total_seconds()
        line.append("  🔄 Resets in ", style="dim")
        line.append(_fmt_duration(secs_left), style="bold green")
        line.append(f"  ({reset_dt.strftime('%b %d')})", style="dim")
    else:
        line.append("  💡 run: ", style="dim")
        line.append("cctoken budget reset-day <day>", style="bold")
        line.append(" to show reset countdown", style="dim")
    return line


_MODEL_COLORS = {
    "claude-opus-4-6": "bright_magenta",
    "claude-sonnet-4-6": "bright_cyan",
    "claude-haiku-4-5-20251001": "bright_green",
}
_MODEL_FALLBACK_COLORS = ["yellow", "blue", "white", "red"]


class _FullWidthModelBar:
    """Full-width stacked model bar, rendered at actual panel width."""

    def __init__(self, model_colors: list[tuple[str, str, int]], total: int):
        self.model_colors = model_colors
        self.total = total

    def __rich_console__(self, console, options):
        width = options.max_width
        bar = Text(no_wrap=True)
        remaining = width
        for i, (short, color, tokens) in enumerate(self.model_colors):
            if i < len(self.model_colors) - 1:
                seg = max(int(tokens / self.total * width), 1) if tokens > 0 else 0
            else:
                seg = remaining
            remaining -= seg
            bar.append("█" * seg, style=color)
        yield bar

        for short, color, tokens in self.model_colors:
            pct = tokens / self.total * 100
            line = Text()
            line.append(f"● {short:<20}", style=f"bold {color}")
            line.append(f"{tokens:>10,}", style="bold cyan")
            line.append(f"  {pct:5.1f}%", style="dim")
            yield line


def _detail_model_panel(records: list[TokenRecord]) -> Panel:
    models = _group_by_model(records)
    if not models:
        return Panel(
            Text("  No usage data", style="dim italic"),
            title="[bold]Model Usage[/bold]",
            border_style="dim",
        )

    total = sum(models.values()) or 1
    sorted_models = sorted(models.items(), key=lambda x: -x[1])

    fallback_idx = 0
    model_colors: list[tuple[str, str, int]] = []
    for model, tokens in sorted_models:
        color = _MODEL_COLORS.get(model)
        if color is None:
            color = _MODEL_FALLBACK_COLORS[fallback_idx % len(_MODEL_FALLBACK_COLORS)]
            fallback_idx += 1
        short = model.replace("claude-", "").replace("-20251001", "")
        model_colors.append((short, color, tokens))

    return Panel(
        _FullWidthModelBar(model_colors, total),
        title="[bold]Model Usage[/bold]",
        border_style="blue",
        padding=(0, 1),
    )


def _detail_project_panel(records: list[TokenRecord], max_rows: int = 10, bar_width: int = 30) -> Panel:
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
            Text("  No sessions recorded", style="dim italic"),
            title="[bold]Projects[/bold]",
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
        content.append(f"{proj:<24}", style="bold magenta" if i == 0 else "magenta")
        content.append("█" * filled, style="bright_cyan" if i == 0 else "cyan")
        content.append("░" * empty, style="dim")
        content.append(f"  {tokens:>10,}", style="bold cyan")
        content.append(f"  {cost_str}", style="green")
        if i < len(rows) - 1:
            content.append("\n")

    return Panel(content, title="[bold]Projects[/bold]", border_style="magenta")


def _build_detail_renderable(records: list[TokenRecord], config: Config, period: str):
    """Build the full renderable for a detail view."""
    from rich.console import Group as RGroup

    now = datetime.now().astimezone()

    if period == "hour":
        block_start, block_end = current_5h_block(now)
        title = f"{block_start.strftime('%H:%M')} – {block_end.strftime('%H:%M')}"
        emoji = "⚡"
        filtered = filter_current_5h_block(records, now)
    elif period == "today":
        title = "Today"
        emoji = "☀️"
        filtered = filter_today(records)
    elif period == "week":
        title = "This Week"
        emoji = "📅"
        filtered = filter_this_week(records)
    else:
        title = "This Month"
        emoji = "📆"
        filtered = filter_this_month(records)

    tokens, cache = _sum_tokens(filtered)
    cost, has_unknown = _sum_cost(filtered)
    cost_str = "~$?.??" if has_unknown else format_cost(cost)

    period_budget, budget_label = _period_budget(config.monthly_token_budget, period, now)

    tz_name = now.strftime("%Z") or now.strftime("%z")

    header = Text(justify="center")
    header.append(f"{emoji}  {title}", style="bold white")
    header.append("  ·  ", style="dim")
    header.append(now.strftime("%Y-%m-%d %H:%M:%S"), style="dim")
    header.append(f"  {tz_name}", style="dim")
    header_panel = Panel(Align.center(header), border_style="bright_magenta", padding=(0, 0))

    status = _status_bar(records, now)
    status_panel = Panel(status, border_style="dim", padding=(0, 0))

    parts = [
        header_panel,
        _detail_budget_bar(tokens, period_budget, label=budget_label, cost_str=cost_str, cache=cache),
        _detail_model_panel(filtered),
        _detail_project_panel(filtered),
        _velocity_panel(records, config, now, period=period),
        status_panel,
    ]
    return RGroup(*parts)


def show_detail_watch(period: str, interval: int = 5) -> None:
    """Live-refresh detail dashboard. Ctrl+C to exit."""
    import shutil
    import sys
    from cctoken.parser import load_all_records
    from cctoken.config import load_config

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
                records = load_all_records()
                config = load_config()
                live.update(_build_detail_renderable(records, config, period))
                next_refresh = now + interval
            time.sleep(0.25)


# Sparkline block characters (9 levels)
_SPARKS = " ▁▂▃▄▅▆▇█"


def _render_spark(values: list[int], width: int, color_high: str = "magenta") -> Text:
    """Render sparkline as Text filling exactly `width` chars."""
    if not values or width <= 0:
        return Text(" " * max(width, 0), style="dim")
    max_val = max(values) or 1
    n = len(values)
    t = Text(no_wrap=True)
    for col in range(width):
        bucket = int(col * n / width)
        v = values[min(bucket, n - 1)]
        idx = int(v / max_val * 8)
        char = _SPARKS[idx]
        if idx == 0:
            t.append(char, style="dim")
        elif idx < 3:
            t.append(char, style="cyan")
        elif idx < 6:
            t.append(char, style="bright_cyan")
        else:
            t.append(char, style=f"bold {color_high}")
    return t


def _render_spark_rows(values: list[int], width: int, height: int, color_high: str = "magenta") -> list[Text]:
    """Render a multi-row sparkline. Returns `height` Text objects (top to bottom)."""
    if not values or width <= 0:
        return [Text(" " * max(width, 0), style="dim") for _ in range(height)]
    max_val = max(values) or 1
    n = len(values)
    total_levels = height * 8
    rows = []
    for row in range(height):
        row_floor = (height - 1 - row) * 8
        t = Text(no_wrap=True)
        for col in range(width):
            bucket = int(col * n / width)
            v = values[min(bucket, n - 1)]
            level = round(v / max_val * total_levels)
            row_level = min(level - row_floor, 8)
            if row_level >= 8:
                char = "█"
            elif row_level > 0:
                char = _SPARKS[row_level]
            else:
                char = " "
            frac = v / max_val
            if char == " ":
                t.append(char, style="dim")
            elif frac < 0.375:
                t.append(char, style="cyan")
            elif frac < 0.75:
                t.append(char, style="bright_cyan")
            else:
                t.append(char, style=f"bold {color_high}")
        rows.append(t)
    return rows


class _Sparkline:
    """Renderable sparkline that fills the full available console width at render time."""

    def __init__(self, values: list[int], min_width: int = 16, color_high: str = "magenta", height: int = 1):
        self.values = values
        self.min_width = min_width
        self.color_high = color_high
        self.height = height

    def __rich_console__(self, console, options):
        width = max(self.min_width, options.max_width)
        if self.height == 1:
            yield _render_spark(self.values, width, self.color_high)
        else:
            for row in _render_spark_rows(self.values, width, self.height, self.color_high):
                yield row


class _Axis:
    """Renderable axis labels that fill the full available console width at render time."""

    def __init__(self, labels: list[str], min_width: int = 16):
        self.labels = labels
        self.min_width = min_width

    def __rich_console__(self, console, options):
        width = max(self.min_width, options.max_width)
        a = [" "] * width
        n = len(self.labels)
        for i, label in enumerate(self.labels):
            pos = round(i * (width - 1) / max(n - 1, 1))
            for j, ch in enumerate(label):
                if pos + j < width:
                    a[pos + j] = ch
        yield Text("".join(a), style="dim", no_wrap=True)


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



def _week_buckets(records: list[TokenRecord]) -> list[int]:
    """7 daily buckets Mon–Sun."""
    from datetime import timedelta
    now = datetime.now().astimezone()
    week_start = (now - timedelta(days=now.weekday())).date()
    days = [week_start + timedelta(days=i) for i in range(7)]
    daily = {d: 0 for d in days}
    for r in records:
        d = r.timestamp.astimezone().date()
        if d in daily:
            daily[d] += r.display_tokens
    return [daily[d] for d in days]


def _month_buckets(records: list[TokenRecord]) -> list[int]:
    """5 weekly buckets for this month."""
    now = datetime.now().astimezone()
    month_start = now.replace(day=1).date()
    buckets = [0] * 5
    for r in records:
        d = r.timestamp.astimezone().date()
        if d >= month_start and d.month == now.month:
            buckets[min((d.day - 1) // 7, 4)] += r.display_tokens
    return buckets



# ── Card builders ─────────────────────────────────────────────────────────────

def _stat_card(
    title: str, emoji: str,
    tokens: int, cost: float, has_unknown: bool,
    spark: _Sparkline,
    axis: _Axis | None = None,
    subtitle: str | None = None,
    border: str = "cyan",
) -> Panel:
    from rich.console import Group as RGroup

    cost_str = "~$?.??" if has_unknown else format_cost(cost)

    tok_line = Text(justify="center")
    tok_line.append(f"{emoji} ", style="bold")
    tok_line.append(f"{tokens:,}", style="bold cyan")
    tok_line.append(" tok", style="dim")

    parts: list = [tok_line]
    if subtitle:
        parts.append(Text(subtitle, justify="center", style="dim"))

    parts.append(spark)
    if axis:
        parts.append(axis)

    cost_line = Text(justify="center")
    cost_line.append(cost_str, style="bold green")
    parts.append(cost_line)

    return Panel(
        RGroup(*parts),
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


def _fmt_duration_period(seconds: float, period: str | None) -> str:
    """Format duration with period-appropriate granularity."""
    seconds = int(seconds)
    d, s = divmod(seconds, 86400)
    h, s = divmod(s, 3600)
    m = s // 60
    if period in ("hour", "today"):
        # Show hours and minutes
        total_h = d * 24 + h
        if total_h:
            return f"{total_h}h {m}m"
        return f"{m}m"
    else:
        # week, month: show days and hours
        if d:
            return f"{d}d {h}h"
        if h:
            return f"{h}h {m}m"
        return f"{m}m"


def _burn_hourly_buckets(records: list[TokenRecord], now: datetime) -> list[int]:
    """24 hourly buckets for the last 24 hours (oldest first)."""
    from datetime import timedelta
    buckets = [0] * 24
    for r in records:
        local = r.timestamp.astimezone()
        delta = now - local
        if timedelta() <= delta < timedelta(hours=24):
            # hours_ago=0 is current hour → bucket index 23
            hours_ago = int(delta.total_seconds() // 3600)
            buckets[23 - min(hours_ago, 23)] += r.display_tokens
    return buckets


def _velocity_panel(records: list[TokenRecord], config: Config, now: datetime, period: str | None = None) -> Panel:
    from rich.console import Group as RGroup
    from datetime import timedelta

    lines: list = []

    if period == "hour":
        block_start, block_end = current_5h_block(now)
        filtered_h = filter_current_5h_block(records, now)
        tokens, _ = _sum_tokens(filtered_h)
        elapsed_h = max((now - block_start).total_seconds() / 3600, 0.1)
        rate = tokens / elapsed_h
        rate_line = Text()
        rate_line.append("🔥 ", style="")
        rate_line.append(f"{rate:,.0f}", style="bold yellow")
        rate_line.append(" tok/hr", style="dim")
        rate_line.append(f"  ({block_start.strftime('%H:%M')}–{block_end.strftime('%H:%M')} avg)", style="dim")
        lines.append(rate_line)
        # 5 hourly buckets within block
        start_hour = block_start.hour
        buckets = [0] * 5
        for r in filtered_h:
            h = r.timestamp.astimezone().hour - start_hour
            buckets[max(0, min(h, 4))] += r.display_tokens
        lines.append(_Sparkline(buckets, min_width=16, color_high="yellow", height=3))
        labels = [f"{(start_hour + i) % 24:02d}" for i in range(5)]
        lines.append(_Axis(labels, min_width=16))
        burn_per_hour = rate

    elif period == "today":
        hours_elapsed = max(now.hour + now.minute / 60, 1)
        today_r = filter_today(records)
        tokens, _ = _sum_tokens(today_r)
        rate = tokens / hours_elapsed
        rate_line = Text()
        rate_line.append("🔥 ", style="")
        rate_line.append(f"{rate:,.0f}", style="bold yellow")
        rate_line.append(" tok/hr", style="dim")
        rate_line.append("  (today avg)", style="dim")
        lines.append(rate_line)
        today_vals, _ = _today_buckets(records)
        lines.append(_Sparkline(today_vals, min_width=24, color_high="yellow", height=3))
        lines.append(_Axis(["0", "6", "12", "18", "23"], min_width=24))
        burn_per_hour = rate

    elif period == "week":
        week_r = filter_this_week(records)
        tokens, _ = _sum_tokens(week_r)
        days_elapsed = max(now.weekday() + now.hour / 24, 1)
        rate = tokens / days_elapsed
        rate_line = Text()
        rate_line.append("🔥 ", style="")
        rate_line.append(f"{rate:,.0f}", style="bold yellow")
        rate_line.append(" tok/day", style="dim")
        rate_line.append("  (this week avg)", style="dim")
        lines.append(rate_line)
        week_vals = _week_buckets(records)
        lines.append(_Sparkline(week_vals, min_width=16, color_high="yellow", height=3))
        lines.append(_Axis(["M", "T", "W", "T", "F", "S", "S"], min_width=16))
        burn_per_hour = rate / 24

    elif period == "month":
        month_r = filter_this_month(records)
        tokens, _ = _sum_tokens(month_r)
        days_elapsed = max(now.day - 1 + now.hour / 24, 1)
        rate = tokens / days_elapsed
        rate_line = Text()
        rate_line.append("🔥 ", style="")
        rate_line.append(f"{rate:,.0f}", style="bold yellow")
        rate_line.append(" tok/day", style="dim")
        rate_line.append("  (this month avg)", style="dim")
        lines.append(rate_line)
        import calendar
        days_in_month = calendar.monthrange(now.year, now.month)[1]
        daily = [0] * days_in_month
        for r in month_r:
            daily[r.timestamp.astimezone().day - 1] += r.display_tokens
        lines.append(_Sparkline(daily, min_width=16, color_high="yellow", height=3))
        lines.append(_Axis(["1", str(days_in_month // 2), str(days_in_month)], min_width=16))
        burn_per_hour = rate / 24

    else:
        # Main dashboard: 24h view
        cutoff_24h = now - timedelta(hours=24)
        recent = [r for r in records if r.timestamp.astimezone() >= cutoff_24h]
        tokens_24h, _ = _sum_tokens(recent)
        burn_per_hour = tokens_24h / 24
        rate_line = Text()
        rate_line.append("🔥 ", style="")
        rate_line.append(f"{burn_per_hour:,.0f}", style="bold yellow")
        rate_line.append(" tok/hr", style="dim")
        rate_line.append("  (last 24h avg)", style="dim")
        lines.append(rate_line)
        burn_buckets = _burn_hourly_buckets(records, now)
        lines.append(_Sparkline(burn_buckets, min_width=24, color_high="yellow", height=3))
        h_now = now.hour
        axis_labels = [f"{(h_now - 23 + i) % 24:02d}" for i in [0, 6, 12, 18, 23]]
        lines.append(_Axis(axis_labels, min_width=24))

    # Budget depletion estimate — period-specific
    if config.monthly_token_budget is not None:
        period_budget, _ = _period_budget(config.monthly_token_budget, period or "month", now)
        # Get period usage
        if period == "hour":
            period_used, _ = _sum_tokens(filter_current_5h_block(records, now))
        elif period == "today":
            period_used, _ = _sum_tokens(filter_today(records))
        elif period == "week":
            period_used, _ = _sum_tokens(filter_this_week(records))
        else:
            period_used, _ = _sum_tokens(filter_this_month(records))
        remaining = (period_budget or 0) - period_used

        dep_line = Text()
        if burn_per_hour > 0 and remaining > 0:
            hours_left = remaining / burn_per_hour
            secs = hours_left * 3600
            dep_line.append("📉 ", style="")
            dep_line.append("budget runs out in ", style="dim")
            is_critical = hours_left < 1 if period == "hour" else hours_left < 24
            dep_line.append(_fmt_duration_period(secs, period), style="bold red" if is_critical else "bold cyan")
            dep_line.append(f"  ({remaining:,} tok left)", style="dim")
        elif remaining <= 0:
            dep_line.append("🚨 ", style="")
            dep_line.append("budget exhausted", style="bold red")
        else:
            dep_line.append("📉 ", style="")
            dep_line.append("no recent activity to estimate", style="dim")
        lines.append(dep_line)

    # Reset countdown — period-specific
    if period == "hour":
        _, block_end = current_5h_block(now)
        secs_left = (block_end - now).total_seconds()
        reset_line = Text()
        reset_line.append("🔄 ", style="")
        reset_line.append(f"resets at {block_end.strftime('%H:%M')} in ", style="dim")
        reset_line.append(_fmt_duration_period(secs_left, "hour"), style="bold green")
        lines.append(reset_line)
    elif period == "today":
        tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        secs_left = (tomorrow - now).total_seconds()
        reset_line = Text()
        reset_line.append("🔄 ", style="")
        reset_line.append("resets at midnight in ", style="dim")
        reset_line.append(_fmt_duration_period(secs_left, "today"), style="bold green")
        lines.append(reset_line)
    elif period == "week":
        days_until_mon = (7 - now.weekday()) % 7 or 7
        next_mon = (now + timedelta(days=days_until_mon)).replace(hour=0, minute=0, second=0, microsecond=0)
        secs_left = (next_mon - now).total_seconds()
        reset_line = Text()
        reset_line.append("🔄 ", style="")
        reset_line.append("resets next Monday in ", style="dim")
        reset_line.append(_fmt_duration_period(secs_left, "week"), style="bold green")
        lines.append(reset_line)
    elif config.billing_reset_day is not None:
        reset_dt = _next_reset(config.billing_reset_day, now)
        secs_left = (reset_dt - now).total_seconds()
        reset_line = Text()
        reset_line.append("🔄 ", style="")
        reset_line.append("resets in ", style="dim")
        reset_line.append(_fmt_duration_period(secs_left, period or "month"), style="bold green")
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
    tz_name = now.strftime("%Z") or now.strftime("%z")
    header = Text(justify="center")
    header.append("⚡ Claude Code Token Monitor  ", style="bold white")
    header.append(now.strftime("%Y-%m-%d  %H:%M:%S"), style="dim")
    header.append(f"  {tz_name}", style="dim")
    header_panel = Panel(Align.center(header), border_style="bright_magenta", padding=(0, 0))

    # ── Stat cards ────────────────────────────────────────────────────────────
    hour_vals, hour_range = _hour_buckets(records)
    today_vals, _         = _today_buckets(records)
    week_vals             = _week_buckets(records)
    month_vals            = _month_buckets(records)

    # Min inner width: wide enough for axis labels to be readable.
    # _Sparkline / _Axis use __rich_console__ to fill the actual panel width at render time.
    CARD_MIN_INNER = 16

    def make_card(title, emoji, recs, raw_vals, axis=None, subtitle=None, border="cyan"):
        tokens, _ = _sum_tokens(recs)
        cost, unk = _sum_cost(recs)
        return _stat_card(
            title, emoji, tokens, cost, unk,
            _Sparkline(raw_vals, min_width=CARD_MIN_INNER),
            axis, subtitle, border,
        )

    stat_panels = [
        make_card("Hour",       "⚡", hour_r,  hour_vals,
                  subtitle=hour_range,
                  border="bright_cyan"),
        make_card("Today",      "☀️ ", today_r, today_vals,
                  axis=_Axis(["0","6","12","18","23"], min_width=CARD_MIN_INNER),
                  border="cyan"),
        make_card("This Week",  "📅", week_r,  week_vals,
                  axis=_Axis(["M","T","W","T","F","S","S"], min_width=CARD_MIN_INNER),
                  border="blue"),
        make_card("This Month", "📆", month_r, month_vals,
                  axis=_Axis(["W1","W2","W3","W4","W5"], min_width=CARD_MIN_INNER),
                  border="magenta"),
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
