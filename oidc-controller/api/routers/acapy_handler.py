import json
import structlog
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from pymongo.database import Database

from ..authSessions.crud import AuthSessionCRUD
from ..authSessions.models import AuthSession, AuthSessionPatch, AuthSessionState
from ..core.acapy.client import AcapyClient
from ..db.session import get_db

from ..core.config import settings
from ..routers.socketio import sio, connections_reload

logger = structlog.getLogger(__name__)

router = APIRouter()


async def _parse_webhook_body(request: Request):
    return json.loads((await request.body()).decode("ascii"))


@router.post("/message-received")
async def post_topic(request: Request, db: Database = Depends(get_db)):
    """Called by Service Agent."""
    logger.info(f">>> message-received")
    webhook_body = await _parse_webhook_body(request)
    logger.info(f">>>> body: {webhook_body}"
    )    
    topic = webhook_body["message"]["type"]

    client = AcapyClient()
    match topic:
        case "identity-proof-submit":
            
            pres_exch_id = webhook_body["message"]["submittedProofItems"][0]["proofExchangeId"]
            logger.info(
                f">>>> pres_exch_id: {pres_exch_id}"
            )

            auth_session: AuthSession = await AuthSessionCRUD(db).get_by_pres_exch_id(
                pres_exch_id
            )

            # Get the saved websocket session
            pid = str(auth_session.id)
            connections = connections_reload()
            sid = connections.get(pid)

            verified = webhook_body["message"]["submittedProofItems"][0]["verified"]

            if verified == True:
                auth_session.proof_status = AuthSessionState.VERIFIED
                await sio.emit("status", {"status": "verified"}, to=sid)
            else:
                auth_session.proof_status = AuthSessionState.FAILED
                await sio.emit("status", {"status": "failed"}, to=sid)

            await AuthSessionCRUD(db).patch(
                str(auth_session.id), AuthSessionPatch(**auth_session.dict())
            )

            # Calcuate the expiration time of the proof
            now_time = datetime.now()
            expired_time = now_time + timedelta(
                seconds=settings.CONTROLLER_PRESENTATION_EXPIRE_TIME
            )

            # Update the expiration time of the proof
            auth_session.expired_timestamp = expired_time
            await AuthSessionCRUD(db).patch(
                str(auth_session.id), AuthSessionPatch(**auth_session.dict())
            )

            # Check if expired. But only if the proof has not been started.
            if (
                expired_time < now_time
                and auth_session.proof_status == AuthSessionState.NOT_STARTED
            ):
                logger.info("EXPIRED")
                auth_session.proof_status = AuthSessionState.EXPIRED
                await sio.emit("status", {"status": "expired"}, to=sid)
                await AuthSessionCRUD(db).patch(
                    str(auth_session.id), AuthSessionPatch(**auth_session.dict())
                )

            pass
        case _:
            logger.debug("skipping webhook")

    return {}
