
from typing import Optional

from fractional_indexing import generate_key_between
from sqlmodel import Session, select

from db.models import Item, UserItemOrder


def get_user_order(session: Session, user_id: int) -> list[UserItemOrder]:
    """Return all UserItemOrder entries for a user, sorted by order_key."""
    return list(session.exec(
        select(UserItemOrder)
        .where(UserItemOrder.user_id == user_id)
        .order_by(UserItemOrder.order_key)
    ).all())


def initialize_user_order(session: Session, user_id: int) -> list[UserItemOrder]:
    """
    Ensure every item owned by user_id has a UserItemOrder entry.
    Items without an entry are appended after existing ones, ordered by item id.
    Returns the full ordered list.
    """
    existing = get_user_order(session, user_id)
    existing_item_ids = {o.item_id for o in existing}

    all_items = session.exec(
        select(Item).where(Item.creator_id == user_id).order_by(Item.id)
    ).all()

    unordered = [item for item in all_items if item.id not in existing_item_ids]

    last_key: Optional[str] = existing[-1].order_key if existing else None
    for item in unordered:
        last_key = generate_key_between(last_key, None)
        session.add(UserItemOrder(user_id=user_id, item_id=item.id, order_key=last_key))

    if unordered:
        session.commit()

    return get_user_order(session, user_id)


def move_item(
    session: Session,
    user_id: int,
    item_id: int,
    after_id: Optional[int],
) -> UserItemOrder:
    """
    Move item_id to immediately follow after_id in user_id's ordering.
    Pass after_id=None to move the item to the front.
    """
    ordered = initialize_user_order(session, user_id)
    order_map = {o.item_id: o for o in ordered}

    # Build the sequence with the moved item removed.
    sequence = [o.item_id for o in ordered if o.item_id != item_id]

    if after_id is None:
        before_key: Optional[str] = None
        after_key: Optional[str] = order_map[sequence[0]].order_key if sequence else None
    else:
        pos = sequence.index(after_id)
        before_key = order_map[after_id].order_key
        after_key = order_map[sequence[pos + 1]].order_key if pos + 1 < len(sequence) else None

    entry = order_map[item_id]
    entry.order_key = generate_key_between(before_key, after_key)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry
