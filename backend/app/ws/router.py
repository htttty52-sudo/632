import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.auth.jwt_utils import verify_token
from app.ws.broadcast import connection_manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/market")
async def market_websocket(websocket: WebSocket, token: str = Query(...)):
    payload = verify_token(token)
    if payload is None:
        await websocket.close(code=4001, reason="Invalid token")
        return

    await connection_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        connection_manager.disconnect(websocket)
