from datetime import datetime, timezone

import pytest

from conftest import load_script

mod = load_script("cc_usage")
pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def test_format_dollars_pads_to_four_places():
    assert mod.format_dollars(0) == "$0.0000"
    assert mod.format_dollars(1.23456789) == "$1.2346"


@pytest.mark.parametrize(
    "value,expected",
    [
        (0, "0"),
        (999, "999"),
        (1_000, "1.0k"),
        (1_500, "1.5k"),
        (12_345, "12.3k"),
        (999_999, "1000.0k"),
        (1_000_000, "1.0M"),
        (2_500_000, "2.5M"),
    ],
)
def test_format_tokens(value, expected):
    assert mod.format_tokens(value) == expected


# ---------------------------------------------------------------------------
# Date bucketing helpers
# ---------------------------------------------------------------------------


def test_to_date_truncates_to_day():
    assert mod.to_date("2026-06-05T14:30:00.000Z") == "2026-06-05"


def test_to_date_empty_is_unknown():
    assert mod.to_date("") == "unknown"


def test_to_month_truncates_to_month():
    assert mod.to_month("2026-06-05T14:30:00.000Z") == "2026-06"


def test_to_month_empty_is_unknown():
    assert mod.to_month("") == "unknown"


# ---------------------------------------------------------------------------
# Date-window math (deterministic: monkeypatch the date source)
# ---------------------------------------------------------------------------


class _FixedDatetime(datetime):
    """datetime subclass with a frozen now()."""

    _fixed = datetime(2026, 6, 5, 12, 0, 0, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return cls._fixed.replace(tzinfo=None)
        return cls._fixed.astimezone(tz)


@pytest.fixture
def frozen_now(monkeypatch):
    """Freeze mod.datetime.now() at 2026-06-05T12:00:00Z."""
    monkeypatch.setattr(mod, "datetime", _FixedDatetime)
    return _FixedDatetime._fixed


def _entry(ts):
    return {"timestamp": ts}


def test_filter_by_days_none_returns_all(frozen_now):
    entries = [_entry("2020-01-01T00:00:00Z"), _entry("2099-01-01T00:00:00Z")]
    assert mod.filter_by_days(entries, None) == entries


def test_filter_by_days_keeps_inside_window(frozen_now):
    # cutoff = now - 7 days = 2026-05-29T12:00:00Z
    inside = _entry("2026-06-01T00:00:00+00:00")
    boundary_old = _entry("2026-05-28T00:00:00+00:00")  # before cutoff
    result = mod.filter_by_days([inside, boundary_old], 7)
    assert inside in result
    assert boundary_old not in result


def test_filter_by_days_cutoff_is_now_minus_days(frozen_now):
    # Exactly on the cutoff instant should be kept (>= comparison).
    cutoff_iso = (frozen_now - mod.timedelta(days=7)).isoformat()
    on_cutoff = _entry(cutoff_iso)
    just_before = _entry((frozen_now - mod.timedelta(days=7, seconds=1)).isoformat())
    result = mod.filter_by_days([on_cutoff, just_before], 7)
    assert on_cutoff in result
    assert just_before not in result


def test_filter_by_days_empty_input(frozen_now):
    assert mod.filter_by_days([], 30) == []


# ---------------------------------------------------------------------------
# Cost math: tiered_cost / calc_cost (pure, no network)
# ---------------------------------------------------------------------------


def test_tiered_cost_no_rate_is_zero():
    assert mod.tiered_cost(1000, None, None) == 0.0
    assert mod.tiered_cost(1000, 0.0, 0.0) == 0.0


def test_tiered_cost_flat_below_threshold():
    assert mod.tiered_cost(1000, 0.002, 0.004) == pytest.approx(2.0)


def test_tiered_cost_splits_above_threshold():
    tokens = mod.TIER_THRESHOLD + 100_000
    expected = mod.TIER_THRESHOLD * 0.002 + 100_000 * 0.004
    assert mod.tiered_cost(tokens, 0.002, 0.004) == pytest.approx(expected)


def test_tiered_cost_above_threshold_without_tier_rate_is_flat():
    tokens = mod.TIER_THRESHOLD + 100_000
    # No tiered_rate -> flat base_rate applies to all tokens.
    assert mod.tiered_cost(tokens, 0.002, None) == pytest.approx(tokens * 0.002)


def _full_entry(**over):
    base = {
        "input_tokens": 1000,
        "output_tokens": 2000,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "speed": None,
    }
    base.update(over)
    return base


def test_calc_cost_sums_all_token_types():
    mp = {
        "input_cost_per_token": 0.000003,
        "output_cost_per_token": 0.000015,
        "cache_creation_input_token_cost": 0.00000375,
        "cache_read_input_token_cost": 0.0000003,
    }
    entry = _full_entry(
        input_tokens=1000,
        output_tokens=2000,
        cache_creation_input_tokens=4000,
        cache_read_input_tokens=8000,
    )
    expected = (
        1000 * 0.000003
        + 2000 * 0.000015
        + 4000 * 0.00000375
        + 8000 * 0.0000003
    )
    assert mod.calc_cost(entry, mp) == pytest.approx(expected)


def test_calc_cost_fast_multiplier_applied():
    mp = {
        "input_cost_per_token": 0.000003,
        "output_cost_per_token": 0.0,
        "provider_specific_entry": {"fast": 2.0},
    }
    entry = _full_entry(input_tokens=1000, output_tokens=0, speed="fast")
    assert mod.calc_cost(entry, mp) == pytest.approx(1000 * 0.000003 * 2.0)


def test_calc_cost_fast_multiplier_ignored_when_not_fast():
    mp = {
        "input_cost_per_token": 0.000003,
        "output_cost_per_token": 0.0,
        "provider_specific_entry": {"fast": 2.0},
    }
    entry = _full_entry(input_tokens=1000, output_tokens=0, speed=None)
    assert mod.calc_cost(entry, mp) == pytest.approx(1000 * 0.000003)


# ---------------------------------------------------------------------------
# find_model_pricing matching
# ---------------------------------------------------------------------------


def test_find_model_pricing_exact():
    pricing = {"claude-x": {"input_cost_per_token": 1}}
    assert mod.find_model_pricing(pricing, "claude-x") == pricing["claude-x"]


def test_find_model_pricing_anthropic_prefixed():
    pricing = {"anthropic/claude-x": {"input_cost_per_token": 1}}
    assert mod.find_model_pricing(pricing, "claude-x") == pricing["anthropic/claude-x"]


def test_find_model_pricing_missing_returns_none():
    assert mod.find_model_pricing({"other": {}}, "nope") is None


# ---------------------------------------------------------------------------
# aggregate (with pricing injected to avoid network)
# ---------------------------------------------------------------------------


def _record(ts, model="claude-x", **tok):
    base = {
        "timestamp": ts,
        "model": model,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "speed": None,
        "costUSD": None,
    }
    base.update(tok)
    return base


def test_aggregate_groups_by_day(monkeypatch):
    pricing = {"claude-x": {"input_cost_per_token": 0.001, "output_cost_per_token": 0.002}}
    monkeypatch.setattr(mod, "get_pricing", lambda: pricing)
    entries = [
        _record("2026-06-05T01:00:00Z", input_tokens=100, output_tokens=10),
        _record("2026-06-05T02:00:00Z", input_tokens=200, output_tokens=20),
        _record("2026-06-04T01:00:00Z", input_tokens=50, output_tokens=5),
    ]
    groups = mod.aggregate(entries, mod.to_date)
    assert set(groups) == {"2026-06-05", "2026-06-04"}
    day = groups["2026-06-05"]
    assert day["inputTokens"] == 300
    assert day["outputTokens"] == 30
    assert day["totalCost"] == pytest.approx(300 * 0.001 + 30 * 0.002)
    assert day["models"]["claude-x"]["inputTokens"] == 300


def test_aggregate_falls_back_to_costusd_when_no_pricing(monkeypatch):
    monkeypatch.setattr(mod, "get_pricing", lambda: {})
    entries = [_record("2026-06-05T01:00:00Z", model="mystery", costUSD=3.5, input_tokens=10)]
    groups = mod.aggregate(entries, mod.to_date)
    assert groups["2026-06-05"]["totalCost"] == pytest.approx(3.5)
