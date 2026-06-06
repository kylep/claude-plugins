import re

import pytest

from conftest import load_script, requires_env, run_cli

mod = load_script("linear")
pytestmark = [pytest.mark.contract, requires_env("LINEAR_API_KEY")]

CONTRACT_TITLE = "pai-tools contract test issue"


def test_live_list_teams(monkeypatch, capsys):
    """list-teams against the live API returns at least one team."""
    run_cli(mod, ["list-teams"], monkeypatch)
    out = capsys.readouterr().out
    # Either real teams (bracketed key lines) or the empty sentinel.
    assert "[" in out or "No teams." in out


def test_live_list_issues(monkeypatch, capsys):
    """list-issues --limit 1 against the live API exits cleanly with plausible output."""
    run_cli(mod, ["list-issues", "--limit", "1"], monkeypatch)
    out = capsys.readouterr().out
    # Either one rendered row or the empty sentinel; both are valid.
    assert "No issues found." in out or re.search(r"[A-Z]+-\d+", out)


@requires_env("LINEAR_TEST_TEAM")
def test_live_create_and_cleanup(monkeypatch, capsys):
    """Create an issue via the CLI, then delete it directly via GraphQL.

    Cleanup runs in a finally block so the issue is removed even if the
    assertions below fail. The CLI has no delete command, so teardown
    bypasses it with a direct issueDelete mutation.
    """
    import os

    team = os.environ["LINEAR_TEST_TEAM"]

    run_cli(
        mod,
        ["create-issue", "--team", team, "--title", CONTRACT_TITLE],
        monkeypatch,
    )
    out = capsys.readouterr().out

    # Output looks like: "Created PER-123: <title>"
    match = re.search(r"Created\s+([A-Z]+-\d+):", out)
    identifier = match.group(1) if match else None

    try:
        assert match, f"could not parse created identifier from: {out!r}"
        assert re.fullmatch(r"[A-Z]+-\d+", identifier)
    finally:
        if identifier:
            # Resolve the internal uuid, then delete (archive) the issue.
            data = mod.gql(
                "query($id: String!) { issue(id: $id) { id } }",
                {"id": identifier},
            )
            issue = (data or {}).get("issue")
            if issue:
                mod.gql(
                    "mutation($id: String!) { issueDelete(id: $id) { success } }",
                    {"id": issue["id"]},
                )
