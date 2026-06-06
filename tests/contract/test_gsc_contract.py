"""Contract test for gsc.py against the live Google Search Console API.

Auto-skips unless GSC_SITE_URL is set, the google client libraries are
importable, and a cached OAuth token file exists. In CI / dev environments
without credentials this skips cleanly, which is expected.
"""

import os
from pathlib import Path

import pytest

from conftest import load_script, requires_env, run_cli

mod = load_script("gsc")
pytestmark = [pytest.mark.contract, requires_env("GSC_SITE_URL")]

def _token_exists() -> bool:
    token = os.environ.get("GSC_TOKEN_PATH")
    if token:
        return Path(token).exists()
    return mod.TOKEN_PATH.exists()


@pytest.mark.skipif(
    not _token_exists(), reason="no cached OAuth token (GSC_TOKEN_PATH / token.json)"
)
def test_live_search_analytics_returns_plausible_output(monkeypatch, capsys):
    """A read-only search-analytics query returns exit 0 and plausible output."""
    # Checked inside the test so default non-contract runs deselect by marker.
    pytest.importorskip("googleapiclient.discovery")
    run_cli(mod, ["search-analytics", "--limit", "5"], monkeypatch)
    out = capsys.readouterr().out
    assert "Search analytics for" in out or out.startswith("No search analytics data")
