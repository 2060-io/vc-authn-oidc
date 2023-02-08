import base64
import io
import logging
import qrcode

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from oic.oic.message import (
    AccessTokenRequest,
    AccessTokenResponse,
    AuthorizationRequest,
    IdToken,
)

from ..core.logger_util import log_debug
from ..authSessions.crud import AuthSessionCreate, AuthSessionCRUD
from ..core.acapy.client import AcapyClient
from ..core.config import settings
from ..core.oidc.issue_token_service import Token
from ..verificationConfigs.crud import VerificationConfigCRUD

ChallengePollUri = "/poll"
AuthorizeCallbackUri = "/callback"
VerifiedCredentialAuthorizeUri = "/authorize"
VerifiedCredentialTokenUri = "/token"

logger = logging.getLogger(__name__)

router = APIRouter()


@log_debug
@router.get(f"{ChallengePollUri}/{{pid}}")
async def poll_pres_exch_complete(pid: str):
    """Called by authorize webpage to see if request is verified and token issuance can proceed."""
    auth_session = await AuthSessionCRUD.get(pid)
    return {"verified": auth_session.verified}


@log_debug
@router.get(VerifiedCredentialAuthorizeUri, response_class=HTMLResponse)
async def get_authorize(request: Request):
    """Called by oidc platform."""
    logger.debug(f">>> get_authorize")

    # Verify OIDC forward payload
    model = AuthorizationRequest().from_dict(request.query_params._dict)
    model.verify()

    client = AcapyClient()
    ver_config_id = model.get("pres_req_conf_id")

    ver_config = await VerificationConfigCRUD.get(ver_config_id)

    # Create presentation_request to show on screen
    response = client.create_presentation_request(ver_config.generate_proof_request())

    new_auth_session = AuthSessionCreate(
        request_parameters=model.to_dict(),
        ver_config_id=ver_config_id,
        pres_exch_id=response.presentation_exchange_id,
        presentation_exchange=response.dict(),
    )

    # save OIDC AuthSession
    auth_session = await AuthSessionCRUD.create(new_auth_session)
    # QR CONTENTS
    controller_host = settings.CONTROLLER_URL
    url_to_message = (
        controller_host + "/url/pres_exch/" + str(auth_session.pres_exch_id)
    )

    # CREATE an image
    buff = io.BytesIO()
    qrcode.make(url_to_message).save(buff, format="PNG")
    image_contents = base64.b64encode(buff.getvalue()).decode("utf-8")

    return f"""
    <html>
        <script>
        setInterval(function() {{
            fetch('{controller_host}/vc/connect{ChallengePollUri}/{auth_session.pres_exch_id}')
                .then(response => response.json())
                .then(data => {{if (data.verified) {{
                        window.location.replace('{controller_host}/vc/connect{AuthorizeCallbackUri}?pid={auth_session.id}', {{method: 'POST'}});
                    }}
                }})
        }}, 2000);

        </script>
        <head>
            <title>Some HTML in here</title>
        </head>
        <body>
            <h1>AUTHORIZATION REQUEST</h1> 

            <p>{url_to_message}</p>

            <p>Scan this QR code for a connectionless present-proof request</p>
            <p><img src="data:image/jpeg;base64,{image_contents}" alt="{image_contents}" width="300px" height="300px" /></p>

            <p> User waits on this screen until Proof has been presented to the vcauth service agent, then is redirected to</p>
            <a href="http://localhost:5201/vc/connect{AuthorizeCallbackUri}?pid={auth_session.id}">callback url (redirect to kc)</a>
        </body>
    </html>

    """


@log_debug
@router.get("/callback", response_class=RedirectResponse)
async def get_authorize_callback(pid: str):
    """Called by Authorize page when verification is complete"""

    redirect_uri = "http://localhost:8880/auth/realms/vc-authn/broker/vc-authn/endpoint"
    auth_session = await AuthSessionCRUD.get(pid)

    url = (
        redirect_uri
        + "?code="
        + str(auth_session.id)
        + "&state="
        + str(auth_session.request_parameters["state"])
    )
    return RedirectResponse(url)


@log_debug
@router.post(VerifiedCredentialTokenUri)
async def post_token(request: Request):
    """Called by oidc platform to retreive token contents"""
    form = await request.form()
    model = AccessTokenRequest().from_dict(form._dict)

    client = AcapyClient()

    auth_session = await AuthSessionCRUD.get(model.get("code"))
    ver_config = await VerificationConfigCRUD.get(auth_session.ver_config_id)

    presentation = client.get_presentation_request(auth_session.pres_exch_id)

    claims = Token.get_claims(presentation, auth_session, ver_config)

    token = Token(
        issuer="placeholder", audiences=["keycloak"], lifetime=10000, claims=claims
    )

    id_token = IdToken().from_dict(
        token.idtoken_dict(auth_session.request_parameters["nonce"])
    )
    id_token_jwt = id_token.to_jwt()
    values = {
        "token_type": "bearer",
        "id_token": id_token_jwt,
        "access_token": "invalid",
        "aud": "keycloak",
    }

    response = AccessTokenResponse().from_dict(values)
    return response