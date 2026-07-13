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

## Current auth scope

Browser Authorization Code + PKCE and refresh-token exchange are intentionally
not implemented in the initial scaffold. Pass known-good tokens directly or
load them from a token file while endpoint behavior is validated.

## Development checks

```bash
pdm run test
pdm run lint
```
