from fastapi import APIRouter
from app.api.v1.endpoints import auth, customers, documents, kyc, sync

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(customers.router, prefix="/customers", tags=["customers"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(kyc.router, prefix="/kyc", tags=["kyc"])
api_router.include_router(sync.router, prefix="/sync", tags=["sync"])

