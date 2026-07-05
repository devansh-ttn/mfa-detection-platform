from fastapi import APIRouter

from mfa.api.v1 import urls as urls_router

router = APIRouter(prefix="/api/v1")
router.include_router(urls_router.router)
