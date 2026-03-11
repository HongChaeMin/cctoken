import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
from cctoken.parser import parse_record, load_all_records, TokenRecord
from cctoken.parser import (
    filter_today, filter_this_week, filter_this_month,
    filter_last_7_days, group_by_project
)


def make_assistant_line(timestamp, cwd, model, input_t, cache_create, cache_read, output_t):
    return json.dumps({
        "type": "assistant",
        "timestamp": timestamp,
        "sessionId": "test-session",
        "cwd": cwd,
        "message": {
            "model": model,
            "usage": {
                "input_tokens": input_t,
                "cache_creation_input_tokens": cache_create,
                "cache_read_input_tokens": cache_read,
                "output_tokens": output_t,
            }
        }
    })


def make_record_at(dt_local, cwd="/foo", display=100):
    """Create a record with a timezone-aware local datetime."""
    return TokenRecord(
        timestamp=dt_local,
        session_id="s",
        cwd=cwd,
        model="claude-sonnet-4-6",
        input_tokens=display,
        cache_creation_tokens=0,
        cache_read_tokens=0,
        output_tokens=0,
    )


# --- parse_record tests ---

def test_parse_record_basic():
    line = make_assistant_line(
        "2026-03-11T02:56:15Z",
        "/Users/foo/Company/my-project",
        "claude-sonnet-4-6",
        100, 500, 200, 50
    )
    record = parse_record(json.loads(line))
    assert record is not None
    assert record.display_tokens == 150
    assert record.cache_tokens == 700
    assert record.input_tokens == 100
    assert record.cache_creation_tokens == 500
    assert record.cache_read_tokens == 200
    assert record.output_tokens == 50
    assert record.model == "claude-sonnet-4-6"
    assert record.cwd == "/Users/foo/Company/my-project"
    assert record.session_id == "test-session"
    assert record.timestamp.tzinfo is not None


def test_parse_record_skips_non_assistant():
    line = json.loads('{"type":"user","timestamp":"2026-03-11T02:56:15Z"}')
    assert parse_record(line) is None


def test_parse_record_skips_missing_usage():
    line = json.loads(json.dumps({
        "type": "assistant",
        "timestamp": "2026-03-11T02:56:15Z",
        "sessionId": "s",
        "cwd": "/foo",
        "message": {"model": "claude-sonnet-4-6"}
    }))
    assert parse_record(line) is None


def test_parse_record_handles_zero_tokens():
    line = make_assistant_line("2026-03-11T02:56:15Z", "/foo", "claude-sonnet-4-6", 0, 0, 0, 0)
    record = parse_record(json.loads(line))
    assert record is not None
    assert record.display_tokens == 0
    assert record.cache_tokens == 0


def test_load_all_records_reads_multiple_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        proj_dir = Path(tmpdir) / "projects" / "proj1"
        proj_dir.mkdir(parents=True)

        lines = [
            make_assistant_line("2026-03-11T02:00:00Z", "/foo", "claude-sonnet-4-6", 100, 0, 0, 50),
            make_assistant_line("2026-03-11T03:00:00Z", "/bar", "claude-sonnet-4-6", 200, 0, 0, 100),
            '{"type":"user","timestamp":"2026-03-11T02:00:00Z"}',
            'not valid json',
        ]
        (proj_dir / "session.jsonl").write_text("\n".join(lines))

        records = load_all_records(claude_dir=Path(tmpdir))
        assert len(records) == 2
        assert records[0].display_tokens == 150
        assert records[1].display_tokens == 300


# --- filter/group tests ---

def test_filter_today_includes_today_excludes_past():
    now = datetime.now().astimezone()
    today_noon = now.replace(hour=12, minute=0, second=0, microsecond=0)
    two_days_ago = now - timedelta(days=2)
    records = [make_record_at(today_noon), make_record_at(two_days_ago)]
    result = filter_today(records)
    assert len(result) == 1
    assert result[0].timestamp == today_noon


def test_filter_this_week_includes_week_start():
    now = datetime.now().astimezone()
    week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    before_week = week_start - timedelta(hours=1)
    records = [make_record_at(week_start), make_record_at(before_week)]
    result = filter_this_week(records)
    assert len(result) == 1
    assert result[0].timestamp == week_start


def test_filter_this_month_includes_month_start():
    now = datetime.now().astimezone()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    before_month = month_start - timedelta(hours=1)
    records = [make_record_at(month_start), make_record_at(before_month)]
    result = filter_this_month(records)
    assert len(result) == 1


def test_filter_last_7_days_excludes_old():
    now = datetime.now().astimezone()
    recent = now - timedelta(days=3)
    old = now - timedelta(days=8)
    records = [make_record_at(recent), make_record_at(old)]
    result = filter_last_7_days(records)
    assert len(result) == 1
    assert result[0].timestamp == recent


def test_group_by_project():
    now = datetime.now().astimezone()
    records = [
        make_record_at(now, "/Users/foo/Company/proj-a"),
        make_record_at(now, "/Users/foo/Company/proj-a"),
        make_record_at(now, "/Users/foo/Other/proj-b"),
    ]
    groups = group_by_project(records)
    assert "Company/proj-a" in groups
    assert "Other/proj-b" in groups
    assert len(groups["Company/proj-a"]) == 2


def test_group_by_project_short_path():
    now = datetime.now().astimezone()
    records = [make_record_at(now, "/solo")]
    groups = group_by_project(records)
    assert "solo" in groups
