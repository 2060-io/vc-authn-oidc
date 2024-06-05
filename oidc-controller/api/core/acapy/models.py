from typing import Optional, Dict

from pydantic import BaseModel


class WalletDid(BaseModel):
    did: str
    verkey: str
    posture: str


class WalletDidPublicResponse(BaseModel):
    result: Optional[WalletDid] = None


class CreatePresentationResponse(BaseModel):
    proofExchangeId: str
    url: str
    shortUrl: str
