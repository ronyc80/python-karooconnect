"""Manual smoke test for the inferred Karoo/SRAM activity endpoints."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING, Any

from karoo import Karoo

if TYPE_CHECKING:
    from collections.abc import Sequence

DEFAULT_TOKENSTORE = "~/.karooconnect/tokens.json"


def main(argv: Sequence[str] | None = None) -> int:
    """Run the activity smoke test."""
    args = _parse_args(argv)
    api = Karoo.from_token_file(args.tokenstore)

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
        help=f"Path to token JSON file. Default: {DEFAULT_TOKENSTORE}",
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
