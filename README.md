# python-karooconnect

Unofficial Python client for Karoo / SRAM account activity data.

This project starts with the smallest useful surface for validating the
dashboard-backed API:

- token-supplied authentication
- activity listing
- activity details
- FIT download
- FIT import
- activity update and delete

The API endpoints are inferred from the Karoo dashboard and are not official
public API documentation. Expect breakage if SRAM changes dashboard behavior.

## Install for development

```bash
pdm install --group :all
```

Or with an existing environment:

```bash
python -m pip install -e ".[testing,linting]"
```

## Basic usage

```python
from karoo import Karoo

api = Karoo(
    access_token="access-token-from-sram-login",
    refresh_token="optional-refresh-token",
    user_id="sram-user-id",
)

activities = api.get_activities(page=1, per_page=50)
details = api.get_activity_details("activity-id")
fit_bytes = api.download_activity_fit("activity-id")
```

Token files are plain JSON:

```python
from karoo import Karoo, KarooTokens, save_tokens

save_tokens(
    "~/.karooconnect/tokens.json",
    KarooTokens(access_token="...", refresh_token="...", user_id="..."),
)

api = Karoo(tokenstore="~/.karooconnect/tokens.json")
```

## First live smoke test

Use either a repo-local `.env` file or `~/.karooconnect/tokens.json`.

For local repo testing, copy the example file:

```bash
cp .env.example .env
```

Then fill `.env`:

```bash
KAROO_ACCESS_TOKEN=paste-bearer-token-here
KAROO_USER_ID=paste-user-id-here
```

`.env` is ignored by Git. Do not commit it and do not paste the token into
issues, logs, or chat.

The current smoke-test default is `https://dashboard.hammerhead.io/v1`. If the
dashboard request URL you see in browser developer tools uses a different base
or prefix, set the base and prefix to match it. For example, if the request URL
is:

```text
https://example.test/api/v1/users/{user_id}/activities
```

add:

```bash
KAROO_BASE_URL=https://example.test
KAROO_API_PREFIX=/api/v1
```

Alternatively, create `~/.karooconnect/tokens.json`:

```json
{
  "access_token": "paste-bearer-token-here",
  "user_id": "paste-user-id-here"
}
```

To get the current token and user id from your own browser session:

1. Open `https://dashboard.hammerhead.io/` and sign in with your SRAM account.
2. Open browser developer tools and go to the Network tab.
3. Reload the dashboard or open the activities page.
4. Filter requests for `nexus.quarqnet.com` or `activities`.
5. Select a request shaped like `/v1/users/{user_id}/activities`.
6. Copy `{user_id}` from the request URL.
7. Copy the request header `Authorization: Bearer ...` and save only the token
   part after `Bearer ` as `access_token`.

Then run:

```bash
uv --cache-dir .uv-cache run --extra testing python scripts/smoke_activities.py
```

The script calls `get_activities()`, `get_activity_details(first_id)`, and
`download_activity_fit(first_id)`. It prints only counts, IDs, payload type, and
FIT byte size.

## Current auth scope

Browser Authorization Code + PKCE and refresh-token exchange are intentionally
not implemented in the initial scaffold. Pass known-good tokens directly or
load them from a token file while endpoint behavior is validated.

## Development checks

```bash
pdm run test
pdm run lint
```
