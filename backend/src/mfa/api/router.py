from fastapi import APIRouter

from mfa.api.v1 import signals as signals_router
from mfa.api.v1 import urls as urls_router

router = APIRouter(prefix="/api/v1")
router.include_router(urls_router.router)
router.include_router(signals_router.router)
