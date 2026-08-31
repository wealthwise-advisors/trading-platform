"""The signed-in account's own stored things.

Right now that is saved backtest configurations, which used to live in the
browser's localStorage. That looked like persistence and was not: clearing site
data destroyed them, they never followed anyone to a second machine, and they
sat outside every server-side promise web/public/privacy.html makes -- closing
an account could not remove them, because the server had never seen them.

OWNERSHIP
---------
Every function here takes the user from `Depends(auth.require_user)` and passes
`user.id` into a WHERE clause. There is no route that accepts a user id, so
there is no parameter to tamper with; a config belonging to somebody else is
not refused so much as unreachable. This mirrors what
api/routers/backtests.py's _get_or_404 does for results, and for the same
reason.
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api import auth
from db import users as repo

log = logging.getLogger(__name__)
router = APIRouter(prefix="/account", tags=["account"])

#: A named config is form state, not a document. The cap is here so a caller
#: cannot park megabytes per name in a table nothing else bounds.
MAX_PAYLOAD_BYTES = 64_000
MAX_CONFIGS = 100


class SavedConfig(BaseModel):
    name: str
    saved_at: str
    #: The ConfigSnapshot the sidebar round-trips. Opaque here on purpose --
    #: see the payload column comment in db/schema.sql.
    config: dict


class SaveConfigRequest(BaseModel):
    config: dict = Field(default_factory=dict)


@router.get("/configs", response_model=list[SavedConfig])
def list_configs(user=Depends(auth.require_user)):
    out = []
    for row in repo.list_configs(user.id):
        try:
            payload = json.loads(row["payload"])
        except (ValueError, TypeError):
            # A row written by an older shape, or corrupted. Skipping it beats
            # failing the whole list and leaving the panel empty.
            log.warning("unreadable saved config %r for user %s",
                        row["name"], user.id)
            continue
        out.append(SavedConfig(name=row["name"], saved_at=row["saved_at"],
                               config=payload))
    return out


@router.put("/configs/{name}", response_model=SavedConfig)
def save_config(name: str, body: SaveConfigRequest,
                user=Depends(auth.require_user)):
    clean = (name or "").strip()
    if not clean:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Give the config a name.")
    if len(clean) > 80:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "That name is too long (80 characters maximum).")

    payload = json.dumps(body.config, separators=(",", ":"))
    if len(payload.encode("utf-8")) > MAX_PAYLOAD_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "That configuration is too large to save.")

    # Counted per owner, and only for a NEW name -- saving over one of your own
    # existing configs is always allowed, or the limit would lock someone out
    # of editing what they already have.
    existing = repo.list_configs(user.id)
    if len(existing) >= MAX_CONFIGS and clean not in {c["name"] for c in existing}:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"You have reached the limit of {MAX_CONFIGS} saved configurations. "
            f"Delete one to save another.")

    saved_at = repo.save_config(user.id, clean, payload)
    return SavedConfig(name=clean, saved_at=saved_at, config=body.config)


@router.delete("/configs/{name}")
def delete_config(name: str, user=Depends(auth.require_user)):
    # 404 rather than 403 for a name this account does not have, matching the
    # rule the backtest routes follow: a 403 would confirm that somebody else's
    # config exists under that name.
    if not repo.delete_config(user.id, (name or "").strip()):
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            "No saved configuration by that name.")
    return {"ok": True}
