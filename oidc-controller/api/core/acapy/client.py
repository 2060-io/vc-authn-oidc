import json
from typing import Optional, Union
from uuid import UUID

import requests
import structlog

from ..config import settings
from .config import AgentConfig, MultiTenantAcapy, SingleTenantAcapy
from .models import CreatePresentationResponse, WalletDid

_client = None
logger = structlog.getLogger(__name__)

WALLET_DID_URI = "/wallet/did"
PUBLIC_WALLET_DID_URI = "/wallet/did/public"
CREATE_PRESENTATION_REQUEST_URL = "/v1/invitation/presentation-request"
PRESENT_PROOF_RECORDS = "/v1/presentations"


class AcapyClient:
    acapy_host = settings.ACAPY_ADMIN_URL
    service_endpoint = settings.ACAPY_AGENT_URL

    wallet_token: Optional[str] = None
    agent_config: AgentConfig

    def __init__(self):
        if settings.ACAPY_TENANCY == "multi":
            self.agent_config = MultiTenantAcapy()
        elif settings.ACAPY_TENANCY == "single":
            self.agent_config = SingleTenantAcapy()
        else:
            logger.warning("ACAPY_TENANCY not set, assuming SingleTenantAcapy")
            self.agent_config = SingleTenantAcapy()

        if _client:
            return _client
        super().__init__()

    def create_presentation_request(
        self, presentation_request_configuration: dict
    ) -> CreatePresentationResponse:
        logger.debug(">>> create_presentation_request")
        # TODO: Take this from config

        resp_raw = requests.post(
            self.acapy_host + CREATE_PRESENTATION_REQUEST_URL,
            headers=self.agent_config.get_headers(),
            json=presentation_request_configuration,
        )

        resp = json.loads(resp_raw.content)
        result = CreatePresentationResponse.parse_obj(resp)

        logger.debug("<<< create_presenation_request")
        return result

    def get_presentation_request(self, presentation_exchange_id: Union[UUID, str]):
        logger.debug(">>> get_presentation_request")

        resp_raw = requests.get(
            self.acapy_host
            + PRESENT_PROOF_RECORDS
            + "/"
            + str(presentation_exchange_id),
            headers=self.agent_config.get_headers(),
        )

        # TODO: Determine if this should assert it received a json object
        assert resp_raw.status_code == 200, resp_raw.content

        resp = json.loads(resp_raw.content)

        logger.debug(f"<<< get_presentation_request -> {resp}")
        return resp

    def verify_presentation(self, presentation_exchange_id: Union[UUID, str]):
        logger.debug(">>> verify_presentation")

        resp_raw = requests.get(
            self.acapy_host
            + PRESENT_PROOF_RECORDS
            + "/"
            + str(presentation_exchange_id),
            headers=self.agent_config.get_headers(),
        )
        assert resp_raw.status_code == 200, resp_raw.content

        resp = json.loads(resp_raw.content)

        logger.debug(f"<<< verify_presentation -> {resp}")
        return resp