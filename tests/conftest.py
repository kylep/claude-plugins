"""Shared fixtures and helpers for the pai-tools test suites.

Importable from any test module as `from conftest import ...` because pytest
puts this file's directory on sys.path (default prepend import mode).
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS = REPO_ROOT / "plugins" / "pai-tools" / "skills"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

# Logical name -> path of each script under test.
SCRIPTS = {
    "openrouter": "openrouter-usage/scripts/openrouter.py",
    "linear": "linear/scripts/linear.py",
    "discord": "discord/scripts/discord.py",
    "google_news": "google-news/scripts/google_news.py",
    "ga4": "ga4-analytics/scripts/ga4.py",
    "gsc": "google-search-console/scripts/gsc.py",
    "openobserve": "openobserve/scripts/openobserve.py",
    "cc_usage": "cc-usage/scripts/cc_usage.py",
    "bitwarden": "bitwarden-vault/scripts/bitwarden.py",
    "desktop": "macos-desktop-control/scripts/desktop.py",
    "strava": "strava/scripts/strava.py",
}

_module_cache: dict[str, object] = {}


def load_script(name: str):
    """Import a script by logical name and return the module object (cached)."""
    if name in _module_cache:
        return _module_cache[name]
    path = SKILLS / SCRIPTS[name]
    spec = importlib.util.spec_from_file_location(f"paitool_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _module_cache[name] = module
    return module


def load_fixture(*parts: str):
    """Read a JSON fixture from tests/fixtures/<parts...>."""
    with open(FIXTURES.joinpath(*parts), encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Fake HTTP plumbing for integration tests (no network)
# ---------------------------------------------------------------------------


class FakeResponse:
    """Stand-in for the object urlopen() returns (a context manager)."""

    def __init__(self, payload, status: int = 200):
        if isinstance(payload, (bytes, bytearray)):
            self._body = bytes(payload)
        elif payload is None:
            self._body = b""
        else:
            self._body = json.dumps(payload).encode("utf-8")
        self.status = status

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def http_error(code: int, body, url: str = "https://example.test") -> HTTPError:
    """Build an HTTPError whose .read() returns `body` (like a real API error)."""
    raw = body if isinstance(body, (bytes, bytearray)) else json.dumps(body).encode()
    return HTTPError(url, code, "error", {}, io.BytesIO(raw))


class FakeUrlopen:
    """Callable urlopen replacement that records requests and returns canned
    responses. `responses` is either a list (consumed in order) or a callable
    taking the Request and returning a payload / FakeResponse / Exception."""

    def __init__(self, responses):
        self._responses = responses
        self.calls: list = []

    def __call__(self, req, timeout=None, **kwargs):
        self.calls.append(req)
        if callable(self._responses):
            result = self._responses(req)
        else:
            result = self._responses.pop(0)
        if isinstance(result, BaseException):
            raise result
        if isinstance(result, FakeResponse):
            return result
        return FakeResponse(result)

    @property
    def last_request(self):
        return self.calls[-1]

    def request_body(self, index: int = -1):
        """Decode the JSON body sent with a recorded request."""
        data = self.calls[index].data
        return json.loads(data.decode("utf-8")) if data else None


def patch_urlopen(monkeypatch, module, responses) -> FakeUrlopen:
    """Replace `module.urlopen` with a FakeUrlopen and return it for assertions."""
    fake = FakeUrlopen(responses)
    monkeypatch.setattr(module, "urlopen", fake)
    return fake


def run_cli(module, args, monkeypatch) -> None:
    """Invoke a script's main() with the given argv (program name auto-prepended)."""
    monkeypatch.setattr(sys, "argv", ["script"] + [str(a) for a in args])
    module.main()


# ---------------------------------------------------------------------------
# Skip helpers for the contract suite
# ---------------------------------------------------------------------------


def requires_env(*names: str):
    """Skip-marker: skip a contract test unless every env var is set."""
    missing = [n for n in names if not os.environ.get(n)]
    return pytest.mark.skipif(
        bool(missing),
        reason=f"missing env: {', '.join(missing)}",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def scripts():
    """Fixture exposing the load_script helper."""
    return load_script
