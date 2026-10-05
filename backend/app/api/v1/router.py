from fastapi import APIRouter

from app.api.v1.endpoints import auth, patient, reports, slots

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(patient.router, prefix="/patient", tags=["patient"])
api_router.include_router(slots.slots_router, prefix="/slots", tags=["slots"])
api_router.include_router(slots.appointments_router, prefix="/appointments", tags=["appointments"])
