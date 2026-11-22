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


# ── settings and chart templates (upgrade plan, Feature 10) ──────────────────
#
# Settings that lived in each browser's storage, held on the server so the owner's
# laptop and sir's browser show the same chart. The browser keeps a copy as a cache
# (web/src/lib/accountSettings.ts); this is the source of truth.
#
# Only the names below are accepted, each a setting the app already has; the values
# are checked again when the chart reads them (lib/chartStyle.ts etc. fall back to
# their defaults on anything malformed), so a bad document cannot break the chart.

#: The settings document's keys. Every one is an existing browser setting.
SETTING_KEYS = {
    "chartStyle", "vwapLevels", "volumeAvg", "volumeProfile", "deviationColors",
    "zone", "watchlist", "priceAlerts", "favourites", "journal",
}
#: A chart template's keys: the chart's settings plus which studies are on.
TEMPLATE_KEYS = {"chartStyle", "vwapLevels", "volumeAvg", "volumeProfile", "deviationColors", "studies"}
MAX_SETTINGS_BYTES = 512_000      # the journal and alerts are the big ones
MAX_TEMPLATES = 50


def _checked(doc: dict, allowed: set[str], limit: int, what: str) -> str:
    unknown = sorted(set(doc) - allowed)
    if unknown:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown {what}: {', '.join(unknown)}.")
    # Values are the exact strings browser storage holds; a template's studies are on/off flags.
    wrong = sorted(k for k, v in doc.items()
                   if not (isinstance(v, dict) and all(isinstance(f, bool) for f in v.values())
                           if k == "studies" else isinstance(v, str)))
    if wrong:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Wrong kind of value for {', '.join(wrong)}.")
    payload = json.dumps(doc, separators=(",", ":"))
    if len(payload.encode("utf-8")) > limit:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"That {what} is too large to save.")
    return payload


class Settings(BaseModel):
    settings: dict
    #: Increases by one on every save; 0 means "never saved".
    version: int
    updated_at: str | None


class SaveSettingsRequest(BaseModel):
    settings: dict = Field(default_factory=dict)
    #: The version this save was made from. A different one on the server means another
    #: tab or device saved in between: refused with 409, never silently overwritten.
    version: int = Field(ge=0)


@router.get("/settings", response_model=Settings)
def get_settings(user=Depends(auth.require_user)):
    row = repo.get_settings(user.id)
    if not row:
        return Settings(settings={}, version=0, updated_at=None)
    try:
        doc = json.loads(row["payload"])
    except (ValueError, TypeError):
        log.warning("unreadable settings for user %s", user.id)
        doc = {}
    return Settings(settings=doc, version=row["version"], updated_at=row["updated_at"])


@router.put("/settings", response_model=Settings)
def put_settings(body: SaveSettingsRequest, user=Depends(auth.require_user)):
    payload = _checked(body.settings, SETTING_KEYS, MAX_SETTINGS_BYTES, "setting")
    saved = repo.put_settings(user.id, payload, body.version)
    if saved is None:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "These settings were changed in another tab or on another device. "
                            "The latest copy has been loaded; make your change again.")
    return Settings(settings=body.settings, version=saved[0], updated_at=saved[1])


class ChartTemplate(BaseModel):
    name: str
    saved_at: str
    is_default: bool
    template: dict


class SaveTemplateRequest(BaseModel):
    template: dict = Field(default_factory=dict)


def _template_name(name: str) -> str:
    clean = (name or "").strip()
    if not clean:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Give the template a name.")
    if len(clean) > 80:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That name is too long (80 characters maximum).")
    return clean


@router.get("/templates", response_model=list[ChartTemplate])
def list_templates(user=Depends(auth.require_user)):
    out = []
    for row in repo.list_templates(user.id):
        try:
            doc = json.loads(row["payload"])
        except (ValueError, TypeError):
            log.warning("unreadable chart template %r for user %s", row["name"], user.id)
            continue
        out.append(ChartTemplate(name=row["name"], saved_at=row["saved_at"],
                                 is_default=bool(row["is_default"]), template=doc))
    return out


# Declared before /templates/{name}: "default" is a fixed path, not a template name.
@router.delete("/templates/default")
def clear_default_template(user=Depends(auth.require_user)):
    repo.set_default_template(user.id, None)
    return {"ok": True}


@router.put("/templates/{name}", response_model=ChartTemplate)
def save_template(name: str, body: SaveTemplateRequest, user=Depends(auth.require_user)):
    clean = _template_name(name)
    payload = _checked(body.template, TEMPLATE_KEYS, MAX_PAYLOAD_BYTES, "template setting")
    existing = {t["name"]: t for t in repo.list_templates(user.id)}
    if len(existing) >= MAX_TEMPLATES and clean not in existing:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"You have reached the limit of {MAX_TEMPLATES} templates. Delete one to save another.")
    saved_at = repo.save_template(user.id, clean, payload)
    return ChartTemplate(name=clean, saved_at=saved_at,
                         is_default=bool(existing.get(clean, {}).get("is_default")), template=body.template)


@router.delete("/templates/{name}")
def delete_template(name: str, user=Depends(auth.require_user)):
    if not repo.delete_template(user.id, (name or "").strip()):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No template by that name.")
    return {"ok": True}


@router.post("/templates/{name}/default")
def make_default_template(name: str, user=Depends(auth.require_user)):
    if not repo.set_default_template(user.id, (name or "").strip()):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No template by that name.")
    return {"ok": True}
