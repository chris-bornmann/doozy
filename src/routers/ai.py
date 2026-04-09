
import json
import logging
from datetime import date, datetime
from typing import Annotated, Optional

import anthropic
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session, case

from app.config import Settings
from app.security import oauth2_scheme
from constants import Priority, State
from db.items import add, find, get, remove, update
from db.main import get_session
from db.models import Item, User
from routers.users import get_current_user


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
  "operation": "create" | "update" | "delete" | "reorder" | "list" | "unknown",
  "item_id": <integer or null - the ID of the item to act on, if mentioned>,
  "fields": {{
    "name": <string or null>,
    "description": <string or null>,
    "priority": "HIGH" | "MEDIUM" | "LOW" | null,
    "state": "NEW" | "IN_PROGRESS" | "DONE" | "CANCELLED" | null,
    "due_on": <ISO 8601 datetime string or null, e.g. "2026-06-01T00:00:00Z">
  }},
  "error": <string describing why the request cannot be fulfilled, or null>
}}

Rules:
- Set "operation" to "unknown" and populate "error" if the request is unclear or unsupported.
- Only include keys in "fields" that are explicitly mentioned or clearly implied by the request.
- If no fields are relevant (e.g. for delete or list), "fields" may be null or an empty object.
- Resolve relative dates like "tomorrow" or "next week" using today's date above.
- Return ONLY valid JSON — no markdown, no code fences, no explanation.
- The "fields" value and its attributes should not be null.  If there are no attributes return fields with null values.
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
    fields: AIItemFields
    error: Optional[str] = None


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
    logger.debug("Claude raw response: %s", raw)
    # Strip markdown code fences if present (e.g. ```json ... ```)
    start = raw.find("{")
    end   = raw.rfind("}") + 1
    raw   = raw[start:end] if start != -1 else raw
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Claude returned non-JSON: %s", raw)
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
            elif resp.fields.name is not None:
                item = find(session, resp.fields.name)
            if item is not None:
                update(session, item, resp.fields.model_dump(exclude_unset=True, exclude_none=True))
            else:
                resp.error = "Item to update not found"
        case "delete":
            if resp.item_id:
                item = get(session, resp.item_id)
            elif resp.fields.name is not None:
                item = find(session, resp.fields.name)
            if item is not None:
                remove(session, item)
            else:
                resp.error = "Item to delete not found"
        case _:
            resp.error = f"Unsupported operation: {resp.operation}"
        
    return resp


@router.post('/request')
async def ai_request(
    user: Annotated[User, Depends(get_current_user)],
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
        raise HTTPException(status_code=502, detail=str(exc))
