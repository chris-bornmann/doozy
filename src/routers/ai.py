
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from app.rate_limit import limiter
from pydantic import BaseModel
from sqlmodel import Session

from app.config import get_settings
from app.security import oauth2_scheme
from db.main import get_session
from db.models import User
from rbac.dependencies import require_permission
from util.ai import AI, AIResponse, get_ai_facade
import services.ai as ai_service


logger = logging.getLogger(__name__)
_settings = get_settings()

router = APIRouter(
    prefix="/ai",
    tags=["ai"],
    dependencies=[Depends(oauth2_scheme)],
    responses={404: {"description": "Not found"}},
)


class AIRequest(BaseModel):
    request: str


@router.post('/request')
@limiter.limit(_settings.RATE_LIMIT_AI)
async def ai_request(
    request: Request,
    user: Annotated[User, Depends(require_permission("ai", "use"))],
    data: AIRequest,
    session: Annotated[Session, Depends(get_session)],
    ai: Annotated[AI, Depends(get_ai_facade)],
) -> AIResponse:
    if not _settings.ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="AI features are not configured")
    try:
        resp: AIResponse = ai.parse_item_request(data.request)
        if resp.error:
            return resp
        return ai_service.handle_ai_response(user, resp, session)
    except ValueError as exc:
        print(str(exc))
        raise HTTPException(status_code=502, detail=str(exc))


@router.post('/voice')
@limiter.limit(_settings.RATE_LIMIT_AI)
async def ai_voice_request(
    request: Request,
    user: Annotated[User, Depends(require_permission("ai", "use"))],
    session: Annotated[Session, Depends(get_session)],
    ai: Annotated[AI, Depends(get_ai_facade)],
    audio: UploadFile = File(...),
) -> AIResponse:
    """Takes an audio file and sends it to be converted to text, and then"""
    """sends the text to be converted to an AIResponse."""

    if not _settings.ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="AI features are not configured")
    if not _settings.OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="Voice features are not configured")

    audio_bytes = await audio.read()
    try:
        transcript = ai.transcribe_audio(audio_bytes, audio.filename or "audio.webm")
    except Exception as exc:
        logger.error("Transcription failed: %s", exc)
        raise HTTPException(status_code=502, detail="Transcription failed")

    try:
        resp = ai.parse_item_request(transcript)
        resp.transcript = transcript
        if resp.error:
            return resp
        return ai_service.handle_ai_response(user, resp, session)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
