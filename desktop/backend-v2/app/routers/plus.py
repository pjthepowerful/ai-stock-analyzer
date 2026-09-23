"""
Paula Plus checkout. Same as the original: a mock purchase that grants Plus
without processing any payment. When real billing lands, this is the one
route to swap for a Stripe checkout session + webhook.
"""
from typing import Literal, Optional

from fastapi import APIRouter, Header
from pydantic import BaseModel

from ..bridge import auth
from ..deps import current_user_required

router = APIRouter(prefix="/api/plus", tags=["plus"])


class PurchaseRequest(BaseModel):
    plan: Literal["monthly", "annual"] = "monthly"


@router.post("/purchase")
def purchase(req: PurchaseRequest, authorization: Optional[str] = Header(None)):
    user = current_user_required(authorization)
    auth.set_plus(user["id"], True)
    return {"ok": True, "plus": True, "plan": req.plan}
