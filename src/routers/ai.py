
import io
import json
import logging
from datetime import date, datetime
from typing import Annotated, Optional

import anthropic
import openai
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session, case

from app.config import Settings
from app.security import oauth2_scheme
from constants import Priority, State
from db.items import add, find, get, remove, update
from db.main import get_session
from db.models import Item, User
from rbac.dependencies import require_permission
from routers.forms import ItemFilter


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/ai",
    tags=["ai"],
    dependencies=[Depends(oauth2_scheme)],
    responses={404: {"description": "Not found"}},
)

_SYSTEM_PROMPT_TEMPLATE = """
Today's date is {today}.

You are a task management assistant. Parse the user's natural language request and return a JSON object describing the operation they want to perform on their to-do list items.

Return ONLY a JSON object with this structure:
{{
  "operation": "create" | "update" | "delete" | "list" | "unknown",
  "item_id": <integer or null — the ID of the item to act on, for create/update/delete only>,
  "fields": {{
    "name": <string or null>,
    "description": <string or null>,
    "priority": "HIGH" | "MEDIUM" | "LOW" | null,
    "state": "NEW" | "IN_PROGRESS" | "DONE" | "CANCELLED" | null,
    "due_on": <ISO 8601 datetime string or null, e.g. "2026-06-01T00:00:00Z">
  }},
  "filter": {{
    "name": <substring to match against item name, or null>,
    "state": [<"NEW" | "IN_PROGRESS" | "DONE" | "CANCELLED">, ...],
    "priority": [<"HIGH" | "MEDIUM" | "LOW">, ...],
    "due_after": <ISO 8601 datetime (exclusive lower bound on due date) or null>,
    "due_before": <ISO 8601 datetime (exclusive upper bound on due date) or null>,
    "due_on": <YYYY-MM-DD calendar day for due date, or null>,
    "created_after": <ISO 8601 datetime or null>,
    "created_before": <ISO 8601 datetime or null>,
    "created_on": <YYYY-MM-DD or null>,
    "completed_after": <ISO 8601 datetime or null>,
    "completed_before": <ISO 8601 datetime or null>,
    "completed_on": <YYYY-MM-DD or null>,
    "tags": [<tag name string>, ...]
  }},
  "error": <string describing why the request cannot be fulfilled, or null>
}}

Rules:
- Set "operation" to "unknown" and populate "error" if the request is unclear or unsupported.
- For "create", "update", "delete": populate "fields" with the relevant item attributes; omit "filter".
- For "list" (requests to show, find, search, or list items): populate "filter" with the matching criteria; omit "fields" and "item_id".
  - Only include filter fields that are explicitly mentioned or clearly implied.
  - An empty filter ({{}}) returns all items.
  - "state" and "priority" use OR semantics within each list.
  - "tags" returns items carrying ANY of the named tags.
  - Use "due_after"/"due_before" for relative ranges (e.g. "due in the next 3 days" → due_after=today, due_before=today+3days).
  - Use "due_on"/"created_on"/"completed_on" for exact calendar days.
  - If the user asks to see items "due" on or by a certain date, exclude items in the Done and Cancelled states.
  - If the user asks to see items "due" by a certain date, set the "due_after" date to yesterday.
  - If the user asks to see items "due" within a certain amount of time (like "due in one week" or "due within 10 days") set the "due_after" date to yesterday.
- Resolve relative dates like "tomorrow", "next week", or "this week" using today's date above.
- Return ONLY valid JSON — no markdown, no code fences, no explanation.
- If the request contains a name it doesn't need to have an item_id.
""".strip()


def _build_system_prompt() -> str:
    return _SYSTEM_PROMPT_TEMPLATE.format(today=date.today().isoformat())


class AIRequest(BaseModel):
    request: str


def _parse_enum(enum_class, v):
    """Coerce a string *v* to *enum_class* by upper-cased name; pass through anything else."""
    return enum_class[v.upper()] if isinstance(v, str) else v


class AIItemFields(BaseModel):
    name: Optional[str] = Field(default=None, max_length=32)
    description: Optional[str] = Field(default=None, max_length=128)
    priority: Optional[Priority] = Field(default=None)
    state: Optional[State] = Field(default=None)
    due_on: Optional[datetime] = Field(default=None)

    @field_validator('priority', mode='before')
    @classmethod
    def parse_priority(cls, v):
        return _parse_enum(Priority, v)

    @field_validator('state', mode='before')
    @classmethod
    def parse_state(cls, v):
        return _parse_enum(State, v)


class AIResponse(BaseModel):
    operation: str
    item_id: Optional[int] = None
    fields: Optional[AIItemFields] = None
    filter: Optional[ItemFilter] = None
    error: Optional[str] = None


def transcribe_audio(audio_bytes: bytes, filename: str, api_key: str) -> str:
    """Send audio bytes to OpenAI Whisper and return the transcript."""
    client = openai.OpenAI(api_key=api_key)
    # Whisper needs a file-like object; the .name hint tells it the audio format.
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = filename
    transcript = client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
    )
    return transcript.text


def parse_item_request(request: str, api_key: str) -> AIResponse:
    """Call Claude to parse a natural language item request.

    Raises:
        ValueError: if Claude returns a response that cannot be parsed as JSON.
    """
    client = anthropic.Anthropic(api_key=api_key)

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=_build_system_prompt(),
        messages=[{"role": "user", "content": request}],
    )

    raw = message.content[0].text

    # Strip markdown code fences if present (e.g. ```json ... ```)
    start = raw.find("{")
    end   = raw.rfind("}") + 1
    raw   = raw[start:end] if start != -1 else raw
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError(f"AI returned an unparseable response: {raw!r}")
    return AIResponse(**parsed)


def _handle_ai_response(
        user: User,
        resp: AIResponse,
        session: Annotated[Session, Depends(get_session)]) -> AIResponse:
    
    item: Optional[Item] = None
    match resp.operation:
        case "create":
            add(session, Item(creator_id=user.id, **resp.fields.model_dump(exclude_unset=True, exclude_none=True)))          
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
                remove(session, item)
            else:
                resp.error = "Item to delete not found"
        case "list":
            pass  # filter is carried in resp.filter; browser calls /items/search
        case _:
            resp.error = f"Unsupported operation: {resp.operation}"
        
    return resp


@router.post('/request')
async def ai_request(
    user: Annotated[User, Depends(require_permission("ai", "use"))],
    data: AIRequest,
    session: Annotated[Session, Depends(get_session)],
) -> AIResponse:
    settings = Settings()
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="AI features are not configured")
    try:
        resp: AIResponse = parse_item_request(data.request, settings.ANTHROPIC_API_KEY)
        if resp.error:
            return resp
        return _handle_ai_response(user, resp, session)
    
    except ValueError as exc:
        print(str(exc))
        raise HTTPException(status_code=502, detail=str(exc))


@router.post('/voice')
async def ai_voice_request(
    user: Annotated[User, Depends(require_permission("ai", "use"))],
    session: Annotated[Session, Depends(get_session)],
    audio: UploadFile = File(...),
) -> AIResponse:
    settings = Settings()
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="AI features are not configured")
    if not settings.OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="Voice features are not configured")

    audio_bytes = await audio.read()
    try:
        transcript = transcribe_audio(audio_bytes, audio.filename or "audio.webm", settings.OPENAI_API_KEY)
    except Exception as exc:
        logger.error("Transcription failed: %s", exc)
        raise HTTPException(status_code=502, detail="Transcription failed")

    try:
        resp = parse_item_request(transcript, settings.ANTHROPIC_API_KEY)
        if resp.error:
            return resp
        return _handle_ai_response(user, resp, session)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
