from __future__ import annotations
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


@dataclass
class TokenRecord:
    timestamp: datetime
    session_id: str
    cwd: str
    model: str
    input_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int
    output_tokens: int

    @property
    def display_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def cache_tokens(self) -> int:
        return self.cache_creation_tokens + self.cache_read_tokens


def parse_record(obj: dict) -> Optional[TokenRecord]:
    """Parse one JSONL object. Returns None if not a valid assistant usage record."""
    if obj.get("type") != "assistant":
        return None

    message = obj.get("message", {})
    usage = message.get("usage")
    if not usage or not isinstance(usage, dict):
        return None

    try:
        ts_str = obj["timestamp"]
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return TokenRecord(
            timestamp=ts,
            session_id=obj.get("sessionId", ""),
            cwd=obj.get("cwd", ""),
            model=message.get("model", "unknown"),
            input_tokens=int(usage.get("input_tokens", 0)),
            cache_creation_tokens=int(usage.get("cache_creation_input_tokens", 0)),
            cache_read_tokens=int(usage.get("cache_read_input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
        )
    except (KeyError, ValueError, TypeError):
        return None


def load_all_records(claude_dir: Optional[Path] = None) -> list[TokenRecord]:
    """Load all TokenRecords from ~/.claude/projects/**/*.jsonl"""
    if claude_dir is None:
        claude_dir = Path.home() / ".claude"

    projects_dir = claude_dir / "projects"
    if not projects_dir.exists():
        print(f"No Claude Code session data found at {projects_dir}")
        print("Make sure Claude Code has been used at least once.")
        return []

    records = []
    for jsonl_file in sorted(projects_dir.glob("**/*.jsonl")):
        try:
            for line in jsonl_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    record = parse_record(obj)
                    if record:
                        records.append(record)
                except json.JSONDecodeError:
                    pass
        except OSError:
            pass

    return records


def _to_local(dt: datetime) -> datetime:
    return dt.astimezone()


def current_5h_block(now: datetime | None = None) -> tuple[datetime, datetime]:
    """Return (block_start, block_end) for the current fixed 5-hour block.
    Blocks: 00-05, 05-10, 10-15, 15-20, 20-01(next day)."""
    if now is None:
        now = datetime.now().astimezone()
    block_idx = now.hour // 5  # 0,1,2,3,4
    start_hour = block_idx * 5
    block_start = now.replace(hour=start_hour, minute=0, second=0, microsecond=0)
    block_end = block_start + timedelta(hours=5)
    return block_start, block_end


def filter_current_5h_block(records: list[TokenRecord], now: datetime | None = None) -> list[TokenRecord]:
    """Filter records in the current fixed 5-hour block."""
    if now is None:
        now = datetime.now().astimezone()
    block_start, _ = current_5h_block(now)
    return [r for r in records if _to_local(r.timestamp) >= block_start and _to_local(r.timestamp) < now + timedelta(seconds=1)]


def filter_this_hour(records: list[TokenRecord]) -> list[TokenRecord]:
    now = datetime.now().astimezone()
    return [
        r for r in records
        if _to_local(r.timestamp).date() == now.date()
        and _to_local(r.timestamp).hour == now.hour
    ]


def filter_today(records: list[TokenRecord]) -> list[TokenRecord]:
    now = datetime.now().astimezone()
    today = now.date()
    return [r for r in records if _to_local(r.timestamp).date() == today]


def filter_this_week(records: list[TokenRecord]) -> list[TokenRecord]:
    now = datetime.now().astimezone()
    week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return [r for r in records if _to_local(r.timestamp) >= week_start]


def filter_this_month(records: list[TokenRecord]) -> list[TokenRecord]:
    now = datetime.now().astimezone()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return [r for r in records if _to_local(r.timestamp) >= month_start]


def filter_last_7_days(records: list[TokenRecord]) -> list[TokenRecord]:
    cutoff = datetime.now().astimezone() - timedelta(days=7)
    return [r for r in records if _to_local(r.timestamp) >= cutoff]


def _project_name(cwd: str) -> str:
    parts = [p for p in cwd.rstrip("/").split("/") if p]
    if len(parts) <= 1:
        return parts[0] if parts else cwd
    return "/".join(parts[-2:])


def group_by_project(records: list[TokenRecord]) -> dict[str, list[TokenRecord]]:
    groups: dict[str, list[TokenRecord]] = {}
    for r in records:
        key = _project_name(r.cwd)
        groups.setdefault(key, []).append(r)
    return groups
