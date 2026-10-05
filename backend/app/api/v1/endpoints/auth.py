import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.models.patient import Patient

router = APIRouter()


class DevTokenRequest(BaseModel):
    patient_id: uuid.UUID


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


@router.post("/token", response_model=TokenResponse)
async def issue_dev_token(payload: DevTokenRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Выдача JWT для разработки и тестов (отключается ENABLE_DEV_TOKEN=false).

    В спецификации нет эндпоинта логина, поэтому для запуска "из коробки" токен выдается по patient_id.
    """
    if not settings.ENABLE_DEV_TOKEN:
        raise HTTPException(status_code=404, detail="Not found")
    if await db.get(Patient, payload.patient_id) is None:
        raise HTTPException(status_code=404, detail="Пациент не найден")
    return TokenResponse(
        access_token=create_access_token(payload.patient_id),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
