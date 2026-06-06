import json

import pytest

from conftest import http_error, load_script, patch_urlopen, run_cli

mod = load_script("linear")
pytestmark = pytest.mark.integration

API_URL = "https://api.linear.app/graphql"
KEY = "lin_api_test"


def _set_key(monkeypatch):
    monkeypatch.setenv("LINEAR_API_KEY", KEY)


def _query_of(req) -> str:
    """Decode a recorded request and return its GraphQL query text."""
    return json.loads(req.data.decode("utf-8"))["query"]


def _vars_of(req) -> dict:
    return json.loads(req.data.decode("utf-8")).get("variables", {})


def _assert_post_auth(req):
    assert req.full_url == API_URL
    assert req.method == "POST"
    assert req.get_header("Authorization") == KEY
    # Raw key, never "Bearer".
    assert "Bearer" not in (req.get_header("Authorization") or "")


# ---------------------------------------------------------------------------
# Canned payloads
# ---------------------------------------------------------------------------


def _issue_node(**over):
    node = {
        "identifier": "PER-1",
        "title": "Fix the thing",
        "state": {"name": "Todo"},
        "priority": 2,
        "assignee": {"displayName": "Kyle"},
        "team": {"key": "PER"},
        "project": {"name": "Platform"},
        "updatedAt": "2026-01-01T00:00:00.000Z",
        "url": "https://linear.app/x/issue/PER-1",
    }
    node.update(over)
    return node


# ---------------------------------------------------------------------------
# list-issues
# ---------------------------------------------------------------------------


def test_list_issues_no_filters(monkeypatch, capsys):
    _set_key(monkeypatch)

    def responses(req):
        assert "issues(filter:" in _query_of(req)
        return {"data": {"issues": {"nodes": [_issue_node()]}}}

    fake = patch_urlopen(monkeypatch, mod, responses)
    run_cli(mod, ["list-issues"], monkeypatch)

    out = capsys.readouterr().out
    assert "PER-1" in out
    assert "Todo" in out
    assert "High" in out          # priority 2 -> High
    assert "Kyle" in out
    assert "Platform" in out
    assert "Fix the thing" in out

    _assert_post_auth(fake.last_request)
    # No filters -> empty filter object.
    assert _vars_of(fake.last_request)["filter"] == {}
    assert _vars_of(fake.last_request)["first"] == 25


def test_list_issues_empty(monkeypatch, capsys):
    _set_key(monkeypatch)
    patch_urlopen(monkeypatch, mod, lambda req: {"data": {"issues": {"nodes": []}}})
    run_cli(mod, ["list-issues"], monkeypatch)
    assert "No issues found." in capsys.readouterr().out


def test_list_issues_with_all_filters(monkeypatch, capsys):
    _set_key(monkeypatch)

    def responses(req):
        q = _query_of(req)
        if "viewer" in q:
            return {"data": {"viewer": {"id": "user-me"}}}
        if "teams(" in q:
            return {"data": {"teams": {"nodes": [{"id": "team-1", "name": "Platform", "key": "PER"}]}}}
        if "issues(filter:" in q:
            return {"data": {"issues": {"nodes": [_issue_node()]}}}
        raise AssertionError(f"unexpected query: {q}")

    fake = patch_urlopen(monkeypatch, mod, responses)
    run_cli(
        mod,
        ["list-issues", "--assignee", "me", "--team", "PER", "--state", "Todo", "--query", "thing"],
        monkeypatch,
    )

    out = capsys.readouterr().out
    assert "PER-1" in out

    # Last request is the issues query; inspect the filter it sent.
    issues_req = fake.last_request
    assert "issues(filter:" in _query_of(issues_req)
    filt = _vars_of(issues_req)["filter"]
    conds = filt["and"]
    # assignee resolved to viewer id
    assert {"assignee": {"id": {"eq": "user-me"}}} in conds
    # team resolved to id
    assert {"team": {"id": {"eq": "team-1"}}} in conds
    # state by name
    assert {"state": {"name": {"eq": "Todo"}}} in conds
    # query -> or of title/description containsIgnoreCase
    assert any("or" in c for c in conds)
    or_cond = next(c for c in conds if "or" in c)
    assert {"title": {"containsIgnoreCase": "thing"}} in or_cond["or"]
    assert {"description": {"containsIgnoreCase": "thing"}} in or_cond["or"]

    # The viewer + teams resolution calls were made first.
    queries = [_query_of(c) for c in fake.calls]
    assert any("viewer" in q for q in queries)
    assert any("teams(" in q for q in queries)


# ---------------------------------------------------------------------------
# get-issue
# ---------------------------------------------------------------------------


def test_get_issue_found(monkeypatch, capsys):
    _set_key(monkeypatch)
    node = {
        "identifier": "PER-7",
        "title": "Investigate",
        "state": {"name": "In Progress"},
        "priority": 1,
        "assignee": {"displayName": "Kyle", "email": "kyle@x.com"},
        "team": {"name": "Platform", "key": "PER"},
        "project": {"name": "Infra"},
        "description": "A longer body.",
        "createdAt": "2026-01-01T00:00:00.000Z",
        "updatedAt": "2026-01-02T00:00:00.000Z",
        "url": "https://linear.app/x/issue/PER-7",
        "labels": {"nodes": [{"name": "bug"}, {"name": "p1"}]},
    }
    fake = patch_urlopen(monkeypatch, mod, lambda req: {"data": {"issue": node}})
    run_cli(mod, ["get-issue", "PER-7"], monkeypatch)

    out = capsys.readouterr().out
    assert "# PER-7  Investigate" in out
    assert "State:    In Progress" in out
    assert "Priority: Urgent" in out
    assert "Team:     Platform  (PER)" in out
    assert "Project:  Infra" in out
    assert "Labels:   bug, p1" in out
    assert "A longer body." in out

    _assert_post_auth(fake.last_request)
    assert _vars_of(fake.last_request) == {"id": "PER-7"}


def test_get_issue_not_found_exits(monkeypatch):
    _set_key(monkeypatch)
    patch_urlopen(monkeypatch, mod, lambda req: {"data": {"issue": None}})
    with pytest.raises(SystemExit):
        run_cli(mod, ["get-issue", "PER-999"], monkeypatch)


# ---------------------------------------------------------------------------
# create-issue
# ---------------------------------------------------------------------------


def test_create_issue_resolves_team_then_creates(monkeypatch, capsys):
    _set_key(monkeypatch)

    def responses(req):
        q = _query_of(req)
        if "teams(" in q:
            return {"data": {"teams": {"nodes": [{"id": "team-1", "name": "Platform", "key": "PER"}]}}}
        if "issueCreate" in q:
            return {
                "data": {
                    "issueCreate": {
                        "success": True,
                        "issue": {
                            "identifier": "PER-42",
                            "title": "New task",
                            "url": "https://linear.app/x/issue/PER-42",
                        },
                    }
                }
            }
        raise AssertionError(f"unexpected query: {q}")

    fake = patch_urlopen(monkeypatch, mod, responses)
    run_cli(
        mod,
        ["create-issue", "--team", "PER", "--title", "New task", "--description", "desc", "--priority", "3"],
        monkeypatch,
    )

    out = capsys.readouterr().out
    assert "Created PER-42: New task" in out
    assert "URL: https://linear.app/x/issue/PER-42" in out

    # First call resolves the team.
    assert "teams(" in _query_of(fake.calls[0])
    assert _vars_of(fake.calls[0]) == {"q": "PER"}

    # Second call is issueCreate with the resolved team id in the input.
    create_req = fake.calls[1]
    assert "issueCreate" in _query_of(create_req)
    _assert_post_auth(create_req)
    payload = _vars_of(create_req)["input"]
    assert payload["teamId"] == "team-1"
    assert payload["title"] == "New task"
    assert payload["description"] == "desc"
    assert payload["priority"] == 3
    assert "assigneeId" not in payload


# ---------------------------------------------------------------------------
# update-issue
# ---------------------------------------------------------------------------


def test_update_issue(monkeypatch, capsys):
    _set_key(monkeypatch)

    def responses(req):
        q = _query_of(req)
        if "issue(id:" in q and "issueUpdate" not in q:
            return {"data": {"issue": {"id": "issue-uuid", "team": {"id": "team-1"}}}}
        if "issueUpdate" in q:
            return {"data": {"issueUpdate": {"success": True}}}
        raise AssertionError(f"unexpected query: {q}")

    fake = patch_urlopen(monkeypatch, mod, responses)
    run_cli(mod, ["update-issue", "PER-7", "--title", "Renamed", "--priority", "4"], monkeypatch)

    out = capsys.readouterr().out
    assert "Updated PER-7" in out

    # First resolves the issue by identifier.
    assert _vars_of(fake.calls[0]) == {"id": "PER-7"}
    # Second is the update, keyed by internal uuid.
    update_req = fake.calls[1]
    assert "issueUpdate" in _query_of(update_req)
    _assert_post_auth(update_req)
    v = _vars_of(update_req)
    assert v["id"] == "issue-uuid"
    assert v["input"] == {"title": "Renamed", "priority": 4}


def test_update_issue_not_found_exits(monkeypatch):
    _set_key(monkeypatch)
    patch_urlopen(monkeypatch, mod, lambda req: {"data": {"issue": None}})
    with pytest.raises(SystemExit):
        run_cli(mod, ["update-issue", "PER-7", "--title", "x"], monkeypatch)


def test_update_issue_no_fields_exits(monkeypatch):
    _set_key(monkeypatch)
    patch_urlopen(
        monkeypatch,
        mod,
        lambda req: {"data": {"issue": {"id": "issue-uuid", "team": {"id": "team-1"}}}},
    )
    with pytest.raises(SystemExit):
        run_cli(mod, ["update-issue", "PER-7"], monkeypatch)


# ---------------------------------------------------------------------------
# add-comment
# ---------------------------------------------------------------------------


def test_add_comment(monkeypatch, capsys):
    _set_key(monkeypatch)

    def responses(req):
        q = _query_of(req)
        if "commentCreate" in q:
            return {"data": {"commentCreate": {"success": True, "comment": {"id": "c-1"}}}}
        if "issue(id:" in q:
            return {"data": {"issue": {"id": "issue-uuid"}}}
        raise AssertionError(f"unexpected query: {q}")

    fake = patch_urlopen(monkeypatch, mod, responses)
    run_cli(mod, ["add-comment", "PER-7", "Looks good"], monkeypatch)

    out = capsys.readouterr().out
    assert "Comment added to PER-7" in out

    assert _vars_of(fake.calls[0]) == {"id": "PER-7"}
    comment_req = fake.calls[1]
    assert "commentCreate" in _query_of(comment_req)
    _assert_post_auth(comment_req)
    assert _vars_of(comment_req)["input"] == {"issueId": "issue-uuid", "body": "Looks good"}


def test_add_comment_not_found_exits(monkeypatch):
    _set_key(monkeypatch)
    patch_urlopen(monkeypatch, mod, lambda req: {"data": {"issue": None}})
    with pytest.raises(SystemExit):
        run_cli(mod, ["add-comment", "PER-7", "body"], monkeypatch)


# ---------------------------------------------------------------------------
# list-comments
# ---------------------------------------------------------------------------


def test_list_comments(monkeypatch, capsys):
    _set_key(monkeypatch)
    payload = {
        "data": {
            "issue": {
                "identifier": "PER-7",
                "comments": {
                    "nodes": [
                        {"user": {"displayName": "Kyle"}, "createdAt": "2026-01-01T00:00:00.000Z", "body": "first"},
                        {"user": None, "createdAt": "2026-01-02T00:00:00.000Z", "body": "second"},
                    ]
                },
            }
        }
    }
    fake = patch_urlopen(monkeypatch, mod, lambda req: payload)
    run_cli(mod, ["list-comments", "PER-7"], monkeypatch)

    out = capsys.readouterr().out
    assert "Kyle" in out
    assert "first" in out
    assert "second" in out
    assert "—" in out             # null user rendered as em-dash
    _assert_post_auth(fake.last_request)
    assert _vars_of(fake.last_request) == {"id": "PER-7"}


def test_list_comments_empty(monkeypatch, capsys):
    _set_key(monkeypatch)
    payload = {"data": {"issue": {"identifier": "PER-7", "comments": {"nodes": []}}}}
    patch_urlopen(monkeypatch, mod, lambda req: payload)
    run_cli(mod, ["list-comments", "PER-7"], monkeypatch)
    assert "No comments on PER-7." in capsys.readouterr().out


def test_list_comments_not_found_exits(monkeypatch):
    _set_key(monkeypatch)
    patch_urlopen(monkeypatch, mod, lambda req: {"data": {"issue": None}})
    with pytest.raises(SystemExit):
        run_cli(mod, ["list-comments", "PER-7"], monkeypatch)


# ---------------------------------------------------------------------------
# list-teams
# ---------------------------------------------------------------------------


def test_list_teams(monkeypatch, capsys):
    _set_key(monkeypatch)
    payload = {
        "data": {
            "teams": {
                "nodes": [
                    {"key": "PER", "name": "Platform", "id": "team-1"},
                    {"key": "ENG", "name": "Engineering", "id": "team-2"},
                ]
            }
        }
    }
    fake = patch_urlopen(monkeypatch, mod, lambda req: payload)
    run_cli(mod, ["list-teams"], monkeypatch)

    out = capsys.readouterr().out
    assert "[PER] Platform" in out
    assert "id: team-1" in out
    assert "[ENG] Engineering" in out
    _assert_post_auth(fake.last_request)
    assert "teams" in _query_of(fake.last_request)


def test_list_teams_empty(monkeypatch, capsys):
    _set_key(monkeypatch)
    patch_urlopen(monkeypatch, mod, lambda req: {"data": {"teams": {"nodes": []}}})
    run_cli(mod, ["list-teams"], monkeypatch)
    assert "No teams." in capsys.readouterr().out


# ---------------------------------------------------------------------------
# list-projects
# ---------------------------------------------------------------------------


def test_list_projects_no_team(monkeypatch, capsys):
    _set_key(monkeypatch)
    payload = {
        "data": {
            "projects": {
                "nodes": [
                    {"name": "Infra", "id": "proj-1", "state": "started"},
                    {"name": "Growth", "id": "proj-2", "state": "planned"},
                ]
            }
        }
    }
    fake = patch_urlopen(monkeypatch, mod, lambda req: payload)
    run_cli(mod, ["list-projects"], monkeypatch)

    out = capsys.readouterr().out
    assert "Infra" in out
    assert "id: proj-1" in out
    assert "started" in out
    _assert_post_auth(fake.last_request)
    # No team -> unfiltered projects query, no variables.
    assert _vars_of(fake.last_request) == {}


def test_list_projects_filtered_by_team(monkeypatch, capsys):
    _set_key(monkeypatch)

    def responses(req):
        q = _query_of(req)
        if "teams(" in q:
            return {"data": {"teams": {"nodes": [{"id": "team-1", "name": "Platform", "key": "PER"}]}}}
        if "accessibleTeams" in q:
            return {"data": {"projects": {"nodes": [{"name": "Infra", "id": "proj-1", "state": "started"}]}}}
        raise AssertionError(f"unexpected query: {q}")

    fake = patch_urlopen(monkeypatch, mod, responses)
    run_cli(mod, ["list-projects", "--team", "PER"], monkeypatch)

    out = capsys.readouterr().out
    assert "Infra" in out

    # First resolves team, second filters projects by that team id.
    assert "teams(" in _query_of(fake.calls[0])
    proj_req = fake.calls[1]
    assert "accessibleTeams" in _query_of(proj_req)
    assert _vars_of(proj_req) == {"team": "team-1"}


def test_list_projects_empty(monkeypatch, capsys):
    _set_key(monkeypatch)
    patch_urlopen(monkeypatch, mod, lambda req: {"data": {"projects": {"nodes": []}}})
    run_cli(mod, ["list-projects"], monkeypatch)
    assert "No projects." in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_gql_errors_exit(monkeypatch):
    _set_key(monkeypatch)
    patch_urlopen(
        monkeypatch,
        mod,
        lambda req: {"errors": [{"message": "something broke"}]},
    )
    with pytest.raises(SystemExit):
        run_cli(mod, ["list-teams"], monkeypatch)


def test_http_error_exits(monkeypatch):
    _set_key(monkeypatch)
    patch_urlopen(monkeypatch, mod, [http_error(401, {"errors": ["unauthorized"]})])
    with pytest.raises(SystemExit):
        run_cli(mod, ["list-teams"], monkeypatch)


def test_missing_key_exits_before_network(monkeypatch):
    monkeypatch.delenv("LINEAR_API_KEY", raising=False)
    # No urlopen patch: a network attempt would error rather than SystemExit.
    with pytest.raises(SystemExit):
        run_cli(mod, ["list-teams"], monkeypatch)
