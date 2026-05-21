
from typing import Optional

from sqlmodel import Session

from db.items import create_item, delete_item, find, get, update
from db.models import Item, User
from util.ai import AIResponse


def handle_ai_response(user: User, resp: AIResponse, session: Session) -> AIResponse:
    """
    Execute the operation described by an AI response.
    For update/delete, only the item creator may act.
    """
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
