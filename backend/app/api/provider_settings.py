"""Admin-only AI provider settings endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.auth import AuthContext, require_admin
from app.api.rate_limit import check_session_rate_limit, client_identifier
from app.config import ADMIN_MUTATION_RATE_LIMIT_PER_MINUTE, ADMIN_READ_RATE_LIMIT_PER_MINUTE
from app.db.database import get_db
from app.services.provider_settings_service import (
    ProviderSettingsError,
    ProviderSettingsService,
)


router = APIRouter(prefix="/admin/provider-settings", tags=["admin-provider-settings"])


class ProviderServiceSettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    clear_api_key: bool = False


class ProviderSettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    llm: Optional[ProviderServiceSettingsRequest] = None
    embedding: Optional[ProviderServiceSettingsRequest] = None


@router.get("/")
async def get_provider_settings(
    _request: Request,
    db: Session = Depends(get_db),
    admin: AuthContext = Depends(require_admin),
):
    """Return non-secret provider settings for the admin UI."""
    check_session_rate_limit(
        admin,
        "provider-settings-read",
        ADMIN_READ_RATE_LIMIT_PER_MINUTE,
        60,
    )
    return {
        "status": "success",
        "data": ProviderSettingsService(db).get_public_settings(),
    }


@router.put("/")
async def update_provider_settings(
    request: ProviderSettingsUpdateRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    admin: AuthContext = Depends(require_admin),
):
    """Store provider settings without returning raw API keys."""
    check_session_rate_limit(
        admin,
        "provider-settings-write",
        ADMIN_MUTATION_RATE_LIMIT_PER_MINUTE,
        60,
    )
    try:
        payload = request.model_dump(exclude_unset=True)
        data = ProviderSettingsService(db).update_settings(
            payload,
            audit_context={
                "admin_session": admin.session_id,
                "client_ip": client_identifier(http_request),
            },
        )
        return {"status": "success", "data": data}
    except ProviderSettingsError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
