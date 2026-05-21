
import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from app.rate_limit import limiter
from pydantic import BaseModel
from sqlmodel import Session

from app.config import get_settings
from app.security import oauth2_scheme
from db.items import create_item, delete_item, find, get, update
from db.main import get_session
from db.models import Item, User
from rbac.dependencies import require_permission
from util.ai import AI, AIResponse


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


def get_ai_facade() -> AI:
    """Dependency to provide an AI facade instance with configured API keys."""
    return AI(
        anthropic_api_key=_settings.ANTHROPIC_API_KEY,
        openai_api_key=_settings.OPENAI_API_KEY or ""
    )


def _handle_ai_response(
    user: User,
    resp: AIResponse,
    session: Annotated[Session, Depends(get_session)]) -> AIResponse:

    item: Optional[Item] = None
    match resp.operation:
        case "create":
            create_item(session, user.id, **resp.fields.model_dump(exclude_unset=True, exclude_none=True))
        case "update":
            if resp.item_id:
                item = get(session, resp.item_id)
                if item is not None and item.creator_id != user.id:
                    item = None
            elif resp.fields.name is not None:
                item = find(session, resp.fields.name, user.id)
            if item is not None:
                update(session, item, resp.fields.model_dump(exclude_unset=True, exclude_none=True))
            else:
                resp.error = "Item to update not found"
        case "delete":
            if resp.item_id:
                item = get(session, resp.item_id)
                if item is not None and item.creator_id != user.id:
                    item = None
            elif resp.fields.name is not None:
                item = find(session, resp.fields.name, user.id)
            if item is not None:
                delete_item(session, item)
            else:
                resp.error = "Item to delete not found"
        case "list":
            pass  # filter is carried in resp.filter; browser calls /items/search
        case _:
            resp.error = f"Unsupported operation: {resp.operation}"

    return resp


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
        return _handle_ai_response(user, resp, session)

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
        return _handle_ai_response(user, resp, session)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
