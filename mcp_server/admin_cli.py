import argparse
import json
import os

import httpx


def _build_headers(admin_api_key: str) -> dict[str, str]:
    return {"X-Admin-Key": admin_api_key}


def _request_post(base_url: str, path: str, admin_api_key: str, payload: dict | None = None) -> dict:
    with httpx.Client() as client:
        response = client.post(
            f"{base_url.rstrip('/')}{path}",
            headers=_build_headers(admin_api_key),
            json=payload,
        )
        response.raise_for_status()
        return response.json()


def _list_rule_groups(rule_engine_url: str) -> list[dict]:
    with httpx.Client() as client:
        response = client.get(f"{rule_engine_url.rstrip('/')}/v1/groups")
        response.raise_for_status()
        return response.json()


def _prompt_group_selection(groups: list[dict], allow_multiple: bool) -> list[str]:
    print("\nAvailable rule groups:")
    for index, group in enumerate(groups, 1):
        print(f"  {index}. {group['name']} ({group['id']})")

    if allow_multiple:
        while True:
            raw = input("Select allowed groups by number (comma-separated): ").strip()
            try:
                indexes = [int(part.strip()) for part in raw.split(",") if part.strip()]
                selected = [groups[i - 1]["id"] for i in indexes]
                if selected:
                    return selected
            except (ValueError, IndexError):
                pass
            print(f"  Invalid input. Enter numbers between 1 and {len(groups)}, comma-separated.")

    while True:
        raw = input("Select the default group by number: ").strip()
        try:
            idx = int(raw)
            if 1 <= idx <= len(groups):
                return [groups[idx - 1]["id"]]
        except (ValueError, IndexError):
            pass
        print(f"  Invalid input. Enter a number between 1 and {len(groups)}.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unreal Objects MCP agent admin CLI")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("UO_MCP_BASE_URL", "http://127.0.0.1:8000"),
        help="Base URL of the MCP server admin API.",
    )
    parser.add_argument(
        "--admin-api-key",
        default=os.environ.get("UO_ADMIN_API_KEY"),
        help="Admin API key for the MCP server.",
    )
    parser.add_argument(
        "--rule-engine-url",
        default=os.environ.get("UO_RULE_ENGINE_URL", "http://127.0.0.1:8001"),
        help="Base URL of the Rule Engine API, used for group selection.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    create_agent = subparsers.add_parser("create-agent", help="Create a new agent.")
    create_agent.add_argument("--name", required=True)
    create_agent.add_argument("--description", default="")

    issue_token = subparsers.add_parser("issue-enrollment-token", help="Issue a one-time enrollment token for an agent.")
    issue_token.add_argument("agent_id")
    issue_token.add_argument("--credential-name", required=True)
    issue_token.add_argument("--scope", action="append", dest="scopes", default=[])
    issue_token.add_argument("--default-group-id", default=None)
    issue_token.add_argument("--allowed-group-id", action="append", dest="allowed_group_ids", default=[])

    revoke = subparsers.add_parser("revoke-credential", help="Revoke an existing credential.")
    revoke.add_argument("credential_id")

    return parser


def main(argv: list[str] | None = None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.admin_api_key:
        parser.error("--admin-api-key is required")

    if args.command == "create-agent":
        result = _request_post(
          args.base_url,
          "/v1/admin/agents",
          args.admin_api_key,
          {"name": args.name, "description": args.description},
        )
    elif args.command == "issue-enrollment-token":
        default_group_id = args.default_group_id
        allowed_group_ids = list(args.allowed_group_ids)
        if default_group_id is None or not allowed_group_ids:
            groups = _list_rule_groups(args.rule_engine_url)
            if default_group_id is None:
                default_group_id = _prompt_group_selection(groups, allow_multiple=False)[0]
            if not allowed_group_ids:
                allowed_group_ids = _prompt_group_selection(groups, allow_multiple=True)

        result = _request_post(
          args.base_url,
          f"/v1/admin/agents/{args.agent_id}/enrollment-tokens",
          args.admin_api_key,
          {
            "credential_name": args.credential_name,
            "scopes": args.scopes or [],
            "default_group_id": default_group_id,
            "allowed_group_ids": allowed_group_ids,
          },
        )
    else:
        result = _request_post(
          args.base_url,
          f"/v1/admin/credentials/{args.credential_id}/revoke",
          args.admin_api_key,
          None,
        )

    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
