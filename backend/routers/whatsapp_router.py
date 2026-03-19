"""WhatsApp Baileys proxy – forwards requests to the Baileys HTTP API."""

import os
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user
from models import User

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])

BAILEYS_URL = os.getenv("BAILEYS_API_URL", "http://localhost:3001")


class SendMessageRequest(BaseModel):
    jid: str
    text: str


@router.get("/status")
async def whatsapp_status(_user: User = Depends(get_current_user)):
    """Proxy to Baileys HTTP API /status."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{BAILEYS_URL}/status")
            return resp.json()
    except httpx.ConnectError:
        return {"status": "offline", "error": "Baileys service not running"}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/qr")
async def whatsapp_qr(_user: User = Depends(get_current_user)):
    """Get QR code string for WhatsApp pairing."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{BAILEYS_URL}/qr")
            return resp.json()
    except httpx.ConnectError:
        return {"qr": None, "error": "Baileys service not running"}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/send")
async def whatsapp_send(body: SendMessageRequest, _user: User = Depends(get_current_user)):
    """Send a WhatsApp message via Baileys."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{BAILEYS_URL}/send",
                json={"jid": body.jid, "text": body.text},
            )
            data = resp.json()
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=data.get("error", "Unknown error"))
            return data
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Baileys service not running")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
