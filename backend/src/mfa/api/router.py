from fastapi import APIRouter

from mfa.api.v1 import audit as audit_router
from mfa.api.v1 import blocklist as blocklist_router
from mfa.api.v1 import chat as chat_router
from mfa.api.v1 import classifications as classifications_router
from mfa.api.v1 import evidence as evidence_router
from mfa.api.v1 import prebid as prebid_router
from mfa.api.v1 import reviews as reviews_router
from mfa.api.v1 import signals as signals_router
from mfa.api.v1 import urls as urls_router

router = APIRouter(prefix="/api/v1")
router.include_router(urls_router.router)
router.include_router(signals_router.router)
router.include_router(classifications_router.router)
router.include_router(reviews_router.router)
router.include_router(audit_router.router)
router.include_router(evidence_router.router)
router.include_router(blocklist_router.router)
router.include_router(chat_router.router)
router.include_router(prebid_router.router)
