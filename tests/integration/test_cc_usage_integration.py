import json
from datetime import datetime, timezone

import pytest

from conftest import load_script, run_cli

mod = load_script("cc_usage")
pytestmark = pytest.mark.integration


# Deterministic "now" for the date-window subcommand math.
FROZEN_NOW = datetime(2026, 6, 5, 12, 0, 0, tzinfo=timezone.utc)


class _FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return FROZEN_NOW.replace(tzinfo=None)
        return FROZEN_NOW.astimezone(tz)


# Simple deterministic pricing so cost numbers are predictable and no network
# call is ever made.
FAKE_PRICING = {
    "claude-test": {
        "input_cost_per_token": 0.001,
        "output_cost_per_token": 0.002,
    }
}


@pytest.fixture(autouse=True)
def no_network_no_clock(monkeypatch):
    """Freeze the clock and stub pricing for every integration test."""
    monkeypatch.setattr(mod, "datetime", _FixedDatetime)
    monkeypatch.setattr(mod, "get_pricing", lambda: FAKE_PRICING)


def _usage_record(ts, model="claude-test", **tok):
    """Build a raw JSONL record as Claude Code writes it."""
    usage = {
        "input_tokens": tok.get("input_tokens", 0),
        "output_tokens": tok.get("output_tokens", 0),
        "cache_creation_input_tokens": tok.get("cache_creation_input_tokens", 0),
        "cache_read_input_tokens": tok.get("cache_read_input_tokens", 0),
    }
    return {
        "timestamp": ts,
        "message": {"model": model, "usage": usage},
    }


def _write_jsonl(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")


def _make_config(tmp_path, monkeypatch):
    """Create a config dir, point CLAUDE_CONFIG_DIR at it, return the projects dir."""
    config = tmp_path / "cc"
    projects = config / "projects"
    projects.mkdir(parents=True)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config))
    return projects


# ---------------------------------------------------------------------------
# Normal multi-record case
# ---------------------------------------------------------------------------


def test_daily_aggregates_multiple_records(tmp_path, monkeypatch, capsys):
    projects = _make_config(tmp_path, monkeypatch)
    _write_jsonl(
        projects / "proj-a" / "session1.jsonl",
        [
            _usage_record("2026-06-05T01:00:00Z", input_tokens=1000, output_tokens=500),
            _usage_record("2026-06-05T02:00:00Z", input_tokens=2000, output_tokens=300),
        ],
    )
    _write_jsonl(
        projects / "proj-b" / "session2.jsonl",
        [_usage_record("2026-06-04T10:00:00Z", input_tokens=4000, output_tokens=100)],
    )

    run_cli(mod, ["daily"], monkeypatch)
    out = capsys.readouterr().out

    assert "2026-06-05" in out
    assert "2026-06-04" in out
    # 2026-06-05: in=3000 -> "3.0k", cost = 3000*.001 + 800*.002 = 4.6
    assert "in: 3.0k" in out
    assert "$4.6000" in out
    # Grand total cost = 4.6 + (4000*.001 + 100*.002 = 4.2) = 8.8
    assert "Total: $8.8000" in out


def test_total_breaks_down_by_model(tmp_path, monkeypatch, capsys):
    projects = _make_config(tmp_path, monkeypatch)
    _write_jsonl(
        projects / "p" / "s.jsonl",
        [
            _usage_record("2026-06-05T01:00:00Z", model="claude-test", input_tokens=1000),
            _usage_record("2026-06-05T02:00:00Z", model="claude-test", input_tokens=500),
        ],
    )

    run_cli(mod, ["total"], monkeypatch)
    out = capsys.readouterr().out

    assert "all time" in out
    assert "Total cost: $1.5000" in out  # 1500 * 0.001
    assert "Input tokens: 1.5k" in out
    assert "claude-test: $1.5000" in out


def test_monthly_buckets_by_month(tmp_path, monkeypatch, capsys):
    projects = _make_config(tmp_path, monkeypatch)
    _write_jsonl(
        projects / "p" / "s.jsonl",
        [
            _usage_record("2026-05-31T23:00:00Z", input_tokens=1000),
            _usage_record("2026-06-01T00:00:00Z", input_tokens=1000),
        ],
    )

    # Use a generous window so the May record is not filtered out.
    run_cli(mod, ["monthly", "--days", "365"], monkeypatch)
    out = capsys.readouterr().out

    assert "2026-05" in out
    assert "2026-06" in out


# ---------------------------------------------------------------------------
# Date filtering (deterministic frozen now)
# ---------------------------------------------------------------------------


def test_daily_days_window_filters_old_records(tmp_path, monkeypatch, capsys):
    projects = _make_config(tmp_path, monkeypatch)
    # now = 2026-06-05T12:00Z; --days 7 -> cutoff 2026-05-29T12:00Z
    _write_jsonl(
        projects / "p" / "s.jsonl",
        [
            _usage_record("2026-06-04T00:00:00+00:00", input_tokens=1000),  # inside
            _usage_record("2026-05-01T00:00:00+00:00", input_tokens=9999),  # outside
        ],
    )

    run_cli(mod, ["daily", "--days", "7"], monkeypatch)
    out = capsys.readouterr().out

    assert "2026-06-04" in out
    assert "2026-05-01" not in out
    # Only the in-window record counted.
    assert "Total: $1.0000  in: 1.0k" in out


def test_total_with_days_excludes_outside_window(tmp_path, monkeypatch, capsys):
    projects = _make_config(tmp_path, monkeypatch)
    _write_jsonl(
        projects / "p" / "s.jsonl",
        [
            _usage_record("2026-06-04T00:00:00+00:00", input_tokens=1000),
            _usage_record("2026-01-01T00:00:00+00:00", input_tokens=5000),
        ],
    )

    run_cli(mod, ["total", "--days", "7"], monkeypatch)
    out = capsys.readouterr().out

    assert "last 7 days" in out
    assert "Total cost: $1.0000" in out  # only the 1000-token record


# ---------------------------------------------------------------------------
# Empty / missing data
# ---------------------------------------------------------------------------


def test_daily_empty_projects_dir(tmp_path, monkeypatch, capsys):
    _make_config(tmp_path, monkeypatch)  # exists but no jsonl files
    run_cli(mod, ["daily"], monkeypatch)
    assert "No usage data found." in capsys.readouterr().out


def test_daily_missing_config_dir(tmp_path, monkeypatch, capsys):
    # Point at a path whose projects/ subdir does not exist.
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "does-not-exist"))
    run_cli(mod, ["daily"], monkeypatch)
    assert "No usage data found." in capsys.readouterr().out


def test_total_empty_is_zero(tmp_path, monkeypatch, capsys):
    _make_config(tmp_path, monkeypatch)
    run_cli(mod, ["total"], monkeypatch)
    out = capsys.readouterr().out
    assert "Total cost: $0.0000" in out


# ---------------------------------------------------------------------------
# Malformed input is skipped, not fatal
# ---------------------------------------------------------------------------


def test_malformed_and_non_usage_lines_skipped(tmp_path, monkeypatch, capsys):
    projects = _make_config(tmp_path, monkeypatch)
    path = projects / "p" / "s.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("not json at all\n")
        fh.write("\n")  # blank line
        fh.write(json.dumps({"timestamp": "2026-06-05T01:00:00Z"}) + "\n")  # no usage
        fh.write(
            json.dumps(
                {"timestamp": "2026-06-05T01:00:00Z", "message": {"usage": {"input_tokens": "x"}}}
            )
            + "\n"
        )  # non-int input_tokens
        fh.write(
            json.dumps(_usage_record("2026-06-05T03:00:00Z", input_tokens=1000)) + "\n"
        )  # valid

    run_cli(mod, ["daily"], monkeypatch)
    out = capsys.readouterr().out

    assert "2026-06-05" in out
    assert "Total: $1.0000  in: 1.0k" in out
