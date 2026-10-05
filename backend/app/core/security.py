import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

bearer_scheme = HTTPBearer(auto_error=False)

# Код закрытия WebSocket при невалидном/просроченном токене (из спецификации)
WS_4008_POLICY_VIOLATION = 4008


def create_access_token(patient_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(patient_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def _decode_patient_id(token: str) -> uuid.UUID:
    """Проверяет подпись/срок токена и возвращает patient_id из sub. Бросает jwt.PyJWTError/ValueError."""
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    return uuid.UUID(str(payload["sub"]))


async def get_current_patient_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> uuid.UUID:
    """FastAPI-зависимость: patient_id авторизованного пользователя из JWT."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Невалидный или просроченный токен",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized
    try:
        return _decode_patient_id(credentials.credentials)
    except (jwt.PyJWTError, ValueError, KeyError):
        raise unauthorized


def ensure_patient_access(token_patient_id: uuid.UUID, requested_patient_id: uuid.UUID) -> None:
    """Защита от IDOR: пациент работает только со своим patient_id."""
    if token_patient_id != requested_patient_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ к данным другого пациента запрещен",
        )


def authenticate_ws_token(token: str, patient_id: str) -> Optional[uuid.UUID]:
    """Проверка токена WebSocket. Возвращает patient_id при успехе, иначе None."""
    try:
        token_patient_id = _decode_patient_id(token)
        if token_patient_id != uuid.UUID(patient_id):
            return None
        return token_patient_id
    except (jwt.PyJWTError, ValueError, KeyError):
        return None
