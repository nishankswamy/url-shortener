"""API key auth.

Scope: creating links and reading analytics. Redirects stay public — they have
to, that's the product.

Keys live in the API_KEYS environment variable, comma separated. If it's empty
the app runs in open mode, which is what you want locally and never in
production. `/health` reports which mode is live so you can catch a deploy that
forgot to set them.

This is not a user system. There are no accounts, so every key sees every link.
Per-user link ownership is a schema change, not an auth change, and it isn't
what day one needs.
"""

import hmac

from fastapi import Header, HTTPException

from .config import settings


def require_key(x_api_key: str | None = Header(default=None)) -> None:
    """FastAPI dependency. No-op when no keys are configured."""
    if not settings.api_keys:
        return

    if x_api_key is None:
        raise HTTPException(
            status_code=401,
            detail="Missing X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # compare_digest to keep the comparison constant-time. The timing signal
    # here is tiny, but constant-time comparison is the default you want to be
    # in the habit of reaching for.
    if not any(hmac.compare_digest(x_api_key, key) for key in settings.api_keys):
        raise HTTPException(status_code=403, detail="Invalid API key.")
