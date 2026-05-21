#!/usr/bin/env python3
"""Linear CLI — list, get, create, update issues; add comments; list teams/projects.

Fresh wrapper (not a port — Linear's official MCP server is not open-source).
Calls the Linear GraphQL API at https://api.linear.app/graphql with a
personal API key in the Authorization header.

Setup:
  1. Generate a personal API key in Linear → Settings → API → Personal API keys.
  2. export LINEAR_API_KEY="lin_api_..."

Usage:
  linear.py list-issues [--assignee me|EMAIL|NAME] [--team NAME] [--project NAME]
                        [--state NAME] [--query TEXT] [--limit 25]
  linear.py get-issue PER-123
  linear.py create-issue --team NAME --title "..." [--description "..."]
                         [--assignee me|EMAIL] [--state NAME] [--priority 0-4]
                         [--project NAME] [--labels LABEL,LABEL]
  linear.py update-issue PER-123 [--title ...] [--description ...]
                                  [--assignee ...] [--state ...] [--priority N]
  linear.py add-comment PER-123 "comment body"
  linear.py list-comments PER-123
  linear.py list-teams
  linear.py list-projects [--team NAME]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

API_URL = "https://api.linear.app/graphql"


def get_api_key() -> str:
    key = os.environ.get("LINEAR_API_KEY")
    if not key:
        sys.exit("LINEAR_API_KEY environment variable is not set")
    return key


def gql(query: str, variables: dict | None = None) -> dict[str, Any]:
    body = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    req = Request(
        API_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": get_api_key(),
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        sys.exit(
            f"Linear API HTTP error {e.code}: {e.read().decode('utf-8', errors='replace')}"
        )
    if "errors" in data:
        sys.exit(f"Linear API error: {json.dumps(data['errors'])}")
    return data.get("data", {})


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------


def resolve_team_id(name_or_key: str) -> str:
    data = gql(
        """
        query($q: String!) {
          teams(filter: { or: [{ name: { eq: $q } }, { key: { eq: $q } }] }) {
            nodes { id name key }
          }
        }
        """,
        {"q": name_or_key},
    )
    nodes = data["teams"]["nodes"]
    if not nodes:
        sys.exit(f"No team matching '{name_or_key}'")
    return nodes[0]["id"]


def resolve_user_id(identifier: str) -> str:
    if identifier == "me":
        return gql("query { viewer { id } }")["viewer"]["id"]
    data = gql(
        """
        query($q: String!) {
          users(filter: { or: [{ email: { eq: $q } }, { name: { eq: $q } }, { displayName: { eq: $q } }] }) {
            nodes { id name email }
          }
        }
        """,
        {"q": identifier},
    )
    nodes = data["users"]["nodes"]
    if not nodes:
        sys.exit(f"No user matching '{identifier}'")
    return nodes[0]["id"]


def resolve_state_id(team_id: str, name: str) -> str:
    data = gql(
        """
        query($team: ID!, $name: String!) {
          workflowStates(filter: { team: { id: { eq: $team } }, name: { eq: $name } }) {
            nodes { id name }
          }
        }
        """,
        {"team": team_id, "name": name},
    )
    nodes = data["workflowStates"]["nodes"]
    if not nodes:
        sys.exit(f"No workflow state '{name}' in team")
    return nodes[0]["id"]


def resolve_project_id(name: str) -> str:
    data = gql(
        """
        query($q: String!) {
          projects(filter: { name: { eq: $q } }) { nodes { id name } }
        }
        """,
        {"q": name},
    )
    nodes = data["projects"]["nodes"]
    if not nodes:
        sys.exit(f"No project matching '{name}'")
    return nodes[0]["id"]


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_list_issues(args: argparse.Namespace) -> None:
    conditions: list[dict] = []
    if args.assignee:
        uid = resolve_user_id(args.assignee)
        conditions.append({"assignee": {"id": {"eq": uid}}})
    if args.team:
        conditions.append({"team": {"id": {"eq": resolve_team_id(args.team)}}})
    if args.project:
        conditions.append({"project": {"id": {"eq": resolve_project_id(args.project)}}})
    if args.state:
        conditions.append({"state": {"name": {"eq": args.state}}})
    if args.query:
        conditions.append(
            {
                "or": [
                    {"title": {"containsIgnoreCase": args.query}},
                    {"description": {"containsIgnoreCase": args.query}},
                ]
            }
        )
    filter_obj: dict = {"and": conditions} if conditions else {}

    data = gql(
        """
        query($filter: IssueFilter, $first: Int!) {
          issues(filter: $filter, first: $first, orderBy: updatedAt) {
            nodes {
              identifier title state { name } priority
              assignee { displayName }
              team { key } project { name }
              updatedAt url
            }
          }
        }
        """,
        {"filter": filter_obj, "first": args.limit},
    )
    nodes = data["issues"]["nodes"]
    if not nodes:
        print("No issues found.")
        return
    for n in nodes:
        prio = ["—", "Urgent", "High", "Medium", "Low"][n.get("priority", 0)]
        assignee = (n.get("assignee") or {}).get("displayName") or "—"
        project = (n.get("project") or {}).get("name") or "—"
        print(
            f"{n['identifier']:<10} "
            f"{n['state']['name']:<14} "
            f"{prio:<8} "
            f"{assignee:<18} "
            f"{project:<22} "
            f"{n['title']}"
        )


def cmd_get_issue(args: argparse.Namespace) -> None:
    data = gql(
        """
        query($id: String!) {
          issue(id: $id) {
            identifier title state { name } priority
            assignee { displayName email }
            team { name key } project { name }
            description createdAt updatedAt url
            labels { nodes { name } }
          }
        }
        """,
        {"id": args.identifier},
    )
    n = data.get("issue")
    if not n:
        sys.exit(f"Issue {args.identifier} not found")
    prio = ["None", "Urgent", "High", "Medium", "Low"][n.get("priority", 0)]
    print(f"# {n['identifier']}  {n['title']}")
    print(f"State:    {n['state']['name']}")
    print(f"Priority: {prio}")
    print(f"Assignee: {(n.get('assignee') or {}).get('displayName') or '—'}")
    print(f"Team:     {n['team']['name']}  ({n['team']['key']})")
    project = (n.get("project") or {}).get("name")
    if project:
        print(f"Project:  {project}")
    labels = [lbl["name"] for lbl in n["labels"]["nodes"]]
    if labels:
        print(f"Labels:   {', '.join(labels)}")
    print(f"Updated:  {n['updatedAt']}")
    print(f"URL:      {n['url']}")
    desc = n.get("description")
    if desc:
        print()
        print(desc)


def cmd_create_issue(args: argparse.Namespace) -> None:
    team_id = resolve_team_id(args.team)
    payload: dict[str, Any] = {"teamId": team_id, "title": args.title}
    if args.description:
        payload["description"] = args.description
    if args.assignee:
        payload["assigneeId"] = resolve_user_id(args.assignee)
    if args.state:
        payload["stateId"] = resolve_state_id(team_id, args.state)
    if args.priority is not None:
        payload["priority"] = args.priority
    if args.project:
        payload["projectId"] = resolve_project_id(args.project)
    if args.labels:
        # Resolve labels by name within the team.
        label_names = [l.strip() for l in args.labels.split(",") if l.strip()]
        data = gql(
            """
            query($team: ID!, $names: [String!]!) {
              issueLabels(filter: { team: { id: { eq: $team } }, name: { in: $names } }) {
                nodes { id name }
              }
            }
            """,
            {"team": team_id, "names": label_names},
        )
        ids = [lbl["id"] for lbl in data["issueLabels"]["nodes"]]
        if len(ids) != len(label_names):
            found = {
                lbl["name"] for lbl in data["issueLabels"]["nodes"]
            }
            missing = [n for n in label_names if n not in found]
            sys.exit(f"Labels not found in team: {', '.join(missing)}")
        payload["labelIds"] = ids

    data = gql(
        """
        mutation($input: IssueCreateInput!) {
          issueCreate(input: $input) {
            success
            issue { identifier title url }
          }
        }
        """,
        {"input": payload},
    )
    issue = data["issueCreate"]["issue"]
    print(f"Created {issue['identifier']}: {issue['title']}")
    print(f"URL: {issue['url']}")


def cmd_update_issue(args: argparse.Namespace) -> None:
    issue_data = gql(
        "query($id: String!) { issue(id: $id) { id team { id } } }",
        {"id": args.identifier},
    )
    issue = issue_data.get("issue")
    if not issue:
        sys.exit(f"Issue {args.identifier} not found")
    team_id = issue["team"]["id"]

    payload: dict[str, Any] = {}
    if args.title is not None:
        payload["title"] = args.title
    if args.description is not None:
        payload["description"] = args.description
    if args.assignee is not None:
        payload["assigneeId"] = resolve_user_id(args.assignee)
    if args.state is not None:
        payload["stateId"] = resolve_state_id(team_id, args.state)
    if args.priority is not None:
        payload["priority"] = args.priority

    if not payload:
        sys.exit("No update fields specified.")

    gql(
        """
        mutation($id: String!, $input: IssueUpdateInput!) {
          issueUpdate(id: $id, input: $input) { success }
        }
        """,
        {"id": issue["id"], "input": payload},
    )
    print(f"Updated {args.identifier}")


def cmd_add_comment(args: argparse.Namespace) -> None:
    issue_data = gql(
        "query($id: String!) { issue(id: $id) { id } }",
        {"id": args.identifier},
    )
    issue = issue_data.get("issue")
    if not issue:
        sys.exit(f"Issue {args.identifier} not found")
    gql(
        """
        mutation($input: CommentCreateInput!) {
          commentCreate(input: $input) { success comment { id } }
        }
        """,
        {"input": {"issueId": issue["id"], "body": args.body}},
    )
    print(f"Comment added to {args.identifier}")


def cmd_list_comments(args: argparse.Namespace) -> None:
    data = gql(
        """
        query($id: String!) {
          issue(id: $id) {
            identifier
            comments { nodes { user { displayName } createdAt body } }
          }
        }
        """,
        {"id": args.identifier},
    )
    issue = data.get("issue")
    if not issue:
        sys.exit(f"Issue {args.identifier} not found")
    nodes = issue["comments"]["nodes"]
    if not nodes:
        print(f"No comments on {issue['identifier']}.")
        return
    for c in nodes:
        author = (c.get("user") or {}).get("displayName") or "—"
        print(f"\n[{c['createdAt']}] {author}")
        print(c["body"])


def cmd_list_teams(_args: argparse.Namespace) -> None:
    data = gql(
        "query { teams { nodes { key name id } } }",
    )
    nodes = data["teams"]["nodes"]
    if not nodes:
        print("No teams.")
        return
    for t in nodes:
        print(f"  [{t['key']}] {t['name']}  (id: {t['id']})")


def cmd_list_projects(args: argparse.Namespace) -> None:
    if args.team:
        team_id = resolve_team_id(args.team)
        data = gql(
            """
            query($team: ID!) {
              projects(filter: { accessibleTeams: { id: { eq: $team } } }) {
                nodes { name id state }
              }
            }
            """,
            {"team": team_id},
        )
    else:
        data = gql(
            "query { projects { nodes { name id state } } }",
        )
    nodes = data["projects"]["nodes"]
    if not nodes:
        print("No projects.")
        return
    for p in nodes:
        print(f"  [{p.get('state', '?'):<10}] {p['name']}  (id: {p['id']})")


def main() -> None:
    parser = argparse.ArgumentParser(prog="linear.py", description="Linear CLI.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list-issues", help="List issues with filters.")
    p.add_argument("--assignee", help="'me', email, or display name.")
    p.add_argument("--team", help="Team name or key.")
    p.add_argument("--project", help="Project name.")
    p.add_argument("--state", help="Workflow state name (e.g. 'Todo').")
    p.add_argument("--query", help="Substring match in title/description.")
    p.add_argument("--limit", type=int, default=25)

    p = sub.add_parser("get-issue", help="Get one issue by identifier (e.g. PER-123).")
    p.add_argument("identifier")

    p = sub.add_parser("create-issue", help="Create an issue.")
    p.add_argument("--team", required=True, help="Team name or key.")
    p.add_argument("--title", required=True)
    p.add_argument("--description", default="")
    p.add_argument("--assignee")
    p.add_argument("--state")
    p.add_argument("--priority", type=int, choices=[0, 1, 2, 3, 4])
    p.add_argument("--project")
    p.add_argument("--labels", help="Comma-separated label names.")

    p = sub.add_parser("update-issue", help="Update issue fields.")
    p.add_argument("identifier")
    p.add_argument("--title")
    p.add_argument("--description")
    p.add_argument("--assignee")
    p.add_argument("--state")
    p.add_argument("--priority", type=int, choices=[0, 1, 2, 3, 4])

    p = sub.add_parser("add-comment", help="Add a comment to an issue.")
    p.add_argument("identifier")
    p.add_argument("body")

    p = sub.add_parser("list-comments", help="List comments on an issue.")
    p.add_argument("identifier")

    sub.add_parser("list-teams", help="List all teams.")

    p = sub.add_parser("list-projects", help="List projects.")
    p.add_argument("--team", help="Filter by team name/key.")

    args = parser.parse_args()
    dispatch = {
        "list-issues": cmd_list_issues,
        "get-issue": cmd_get_issue,
        "create-issue": cmd_create_issue,
        "update-issue": cmd_update_issue,
        "add-comment": cmd_add_comment,
        "list-comments": cmd_list_comments,
        "list-teams": cmd_list_teams,
        "list-projects": cmd_list_projects,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
