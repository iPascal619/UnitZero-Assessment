"""Health check and SSE events endpoints."""

import asyncio
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db
from app.events import event_manager
from app.dependencies import get_current_user
from app.models import User

router = APIRouter(tags=["system"])


@router.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    """Health check: returns ok if the API and database are reachable."""
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"

    return {"status": "ok" if db_status == "ok" else "degraded", "database": db_status}


@router.get("/api/events")
async def sse_events(current_user: User = Depends(get_current_user)):
    """Server-Sent Events stream for real-time updates (stretch item).

    Operators/admins receive all events. Clients receive events
    only for their own requests.
    """

    queue = event_manager.subscribe()

    async def event_generator():
        try:
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    # Filter: clients only see their own request events
                    if current_user.role == "client":
                        data = message.get("data", {})
                        if data.get("client_id") and data["client_id"] != current_user.id:
                            continue
                    yield f"event: {message['type']}\ndata: {json.dumps(message['data'])}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            event_manager.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
