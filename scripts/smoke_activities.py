"""Manual smoke test for the inferred Karoo/SRAM activity endpoints."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from karoo import Karoo, KarooClient

if TYPE_CHECKING:
    from collections.abc import Sequence

DEFAULT_TOKENSTORE = "~/.karooconnect/tokens.json"
DEFAULT_ENV_FILE = ".env"
ENV_ACCESS_TOKEN = "KAROO_ACCESS_TOKEN"
ENV_REFRESH_TOKEN = "KAROO_REFRESH_TOKEN"
ENV_USER_ID = "KAROO_USER_ID"
ENV_BASE_URL = "KAROO_BASE_URL"
ENV_API_PREFIX = "KAROO_API_PREFIX"


def main(argv: Sequence[str] | None = None) -> int:
    """Run the activity smoke test."""
    args = _parse_args(argv)
    env = _load_env_file(args.env_file)
    api = _build_api(args.tokenstore, env)
    print(
        "Using API base "
        f"{api.client.base_url}{api.client.api_prefix or ''} "
        f"for user {api.user_id}"
    )

    activities_payload = api.get_activities(page=1, per_page=args.per_page)
    activities = _extract_activities(activities_payload)
    print(f"Loaded {len(activities)} activities")

    if not activities:
        print("No activities returned; token and user_id were accepted.")
        return 0

    first_activity = activities[0]
    activity_id = _extract_activity_id(first_activity)
    print(f"First activity: {activity_id} {_activity_label(first_activity)}")

    details = api.get_activity_details(activity_id)
    print(f"Details payload type: {type(details).__name__}")

    fit_bytes = api.download_activity_fit(activity_id)
    print(f"FIT download size: {len(fit_bytes)} bytes")

    if args.output_dir is not None:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = args.output_dir / f"{activity_id}.fit"
        output_path.write_bytes(fit_bytes)
        print(f"Wrote FIT file: {output_path}")

    return 0


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke-test Karoo/SRAM activity endpoints with a token file.",
    )
    parser.add_argument(
        "--tokenstore",
        default=DEFAULT_TOKENSTORE,
        help=(
            "Path to token JSON file used when env vars are not set. "
            f"Default: {DEFAULT_TOKENSTORE}"
        ),
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(DEFAULT_ENV_FILE),
        help=f"Path to local env file. Default: {DEFAULT_ENV_FILE}",
    )
    parser.add_argument(
        "--per-page",
        type=int,
        default=5,
        help="Number of activities to request from the list endpoint.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Optional directory where the downloaded FIT file should be written.",
    )
    return parser.parse_args(argv)


def _build_api(tokenstore: str, env: dict[str, str]) -> Karoo:
    access_token = _env_value(env, ENV_ACCESS_TOKEN)
    user_id = _env_value(env, ENV_USER_ID)
    refresh_token = _env_value(env, ENV_REFRESH_TOKEN)
    base_url = _env_value(env, ENV_BASE_URL) or "https://dashboard.hammerhead.io"
    api_prefix = _env_value(env, ENV_API_PREFIX) or "/v1"

    if access_token and user_id:
        client = KarooClient(
            access_token=access_token,
            refresh_token=refresh_token,
            base_url=base_url,
            api_prefix=api_prefix,
        )
        return Karoo(client=client, user_id=user_id)

    client = KarooClient(
        tokenstore=tokenstore,
        base_url=base_url,
        api_prefix=api_prefix,
    )
    return Karoo(client=client)


def _env_value(env: dict[str, str], key: str) -> str | None:
    value = os.environ.get(key) or env.get(key)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    lines = path.read_text(encoding="utf-8").splitlines()
    for line_number, raw_line in enumerate(lines, 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        if "=" not in line:
            raise ValueError(f"Invalid env line {line_number}: missing '='")

        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Invalid env line {line_number}: missing key")
        values[key] = _strip_env_quotes(value.strip())
    return values


def _strip_env_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _extract_activities(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [_ensure_activity(item) for item in payload]

    if isinstance(payload, dict):
        for key in ("activities", "items", "data", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [_ensure_activity(item) for item in value]

    raise ValueError(
        "Could not find an activity list in the response. "
        f"Top-level payload type: {type(payload).__name__}"
    )


def _extract_activity_id(activity: dict[str, Any]) -> str:
    for key in ("id", "activityId", "activity_id", "uuid"):
        value = activity.get(key)
        if value is not None and str(value).strip():
            return str(value)
    raise ValueError(f"Could not find an activity id in keys: {sorted(activity)}")


def _activity_label(activity: dict[str, Any]) -> str:
    for key in ("name", "title", "sport", "type", "activityType"):
        value = activity.get(key)
        if value is not None and str(value).strip():
            return f"({key}={value})"
    return ""


def _ensure_activity(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"Activity item must be an object, got {type(value).__name__}")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
