import time
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field

from .examples import ex_ver_config
from ..core.config import settings


# Slightly modified from ACAPY models.
class AttributeFilter(BaseModel):
    schema_id: Optional[str] = None
    cred_def_id: Optional[str] = None
    schema_name: Optional[str] = None
    schema_issuer_did: Optional[str] = None
    schema_version: Optional[str] = None
    issuer_did: Optional[str] = None


class ReqAttr(BaseModel):
    names: List[str]
    label: Optional[str] = None
    restrictions: List[AttributeFilter]


class ReqPred(BaseModel):
    name: str
    label: Optional[str] = None
    restrictions: List[AttributeFilter]
    p_value: str
    p_type: str


class VerificationProofRequest(BaseModel):
    name: Optional[str] = None
    version: str = Field(pattern="[0-9](.[0.9])*", examples=["0.0.1"])
    non_revoked: Optional[str] = None
    requested_attributes: List[ReqAttr]
    requested_predicates: List[ReqPred]

class VerificationRequestedCredentials(BaseModel):
    credentialDefinitionId: str
    attributes: List[str]

class VerificationConfigBase(BaseModel):
    subject_identifier: str = Field()
    # proof_request: VerificationProofRequest = Field()
    requested_credentials: List[VerificationRequestedCredentials] = Field()
    generate_consistent_identifier: Optional[bool] = Field(default=False)
    include_v1_attributes: Optional[bool] = Field(default=False)

    def generate_proof_request(self):
        # result = {
        #     "requestedCredentials":[{
        #         "credentialDefinitionId": self.requested_credentials[0].credentialDefinitionId,
        #         "attributes":self.requested_credentials[0].attributes
        #         }]
        # }
        return {"requestedCredentials":[credential.dict() for credential in self.requested_credentials]}

    model_config = ConfigDict(json_schema_extra={"example": ex_ver_config})


class VerificationConfig(VerificationConfigBase):
    ver_config_id: str = Field()


class VerificationConfigRead(VerificationConfigBase):
    ver_config_id: str = Field()


class VerificationConfigPatch(VerificationConfigBase):
    subject_identifier: Optional[str] = Field(None)
    # proof_request: Optional[VerificationProofRequest] = Field(None)
    requested_credentials: Optional[VerificationRequestedCredentials] = Field(None)

    pass
