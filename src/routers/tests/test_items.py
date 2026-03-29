import datetime as dt

from sqlmodel import Session

from constants import Priority
from db.models import Item
from db.users import create_user


# ---------------------------------------------------------------------------
# POST /items/
# ---------------------------------------------------------------------------

def test_post_item_returns_id(auth_headers):
    client, _ = auth_headers
    response = client.post("/items/", params={"name": "Buy some milk"})
    assert response.status_code == 200
    assert "id" in response.json()


def test_post_item_sets_creator(auth_headers, session):
    client, user = auth_headers
    item_id = client.post("/items/", params={"name": "Buy some milk"}).json()["id"]
    item = session.get(Item, item_id)
    assert item.creator_id == user.id


def test_post_item_requires_auth(client):
    assert client.post("/items/", params={"name": "Buy some milk"}).status_code == 401


def test_post_item_name_too_short(auth_headers):
    client, _ = auth_headers
    # min_length=8 on Item.name
    assert client.post("/items/", params={"name": "abc"}).status_code == 422


# ---------------------------------------------------------------------------
# GET /items/
# ---------------------------------------------------------------------------

def test_read_items_returns_only_own(auth_headers, session):
    client, user = auth_headers
    client.post("/items/", params={"name": "My own task"})

    other = create_user(session, username="otheruser2", password="password1234")
    session.add(Item(name="Not my task!", creator_id=other.id))
    session.commit()

    response = client.get("/items/")
    assert response.status_code == 200
    names = [i["name"] for i in response.json()["items"]]
    assert "My own task" in names
    assert "Not my task!" not in names


def test_read_items_requires_auth(client):
    assert client.get("/items/").status_code == 401


# ---------------------------------------------------------------------------
# GET /items/{id}
# ---------------------------------------------------------------------------

def test_read_item_by_id(auth_headers):
    client, _ = auth_headers
    item_id = client.post("/items/", params={"name": "Read this item"}).json()["id"]
    response = client.get(f"/items/{item_id}")
    assert response.status_code == 200
    assert response.json()["id"] == item_id


def test_read_item_not_found(auth_headers):
    client, _ = auth_headers
    assert client.get("/items/9999").status_code == 404


def test_read_item_wrong_owner_is_forbidden(auth_headers, session):
    client, _ = auth_headers
    other = create_user(session, username="otheruser3", password="password1234")
    item = Item(name="Belongs to other", creator_id=other.id)
    session.add(item)
    session.commit()
    session.refresh(item)
    assert client.get(f"/items/{item.id}").status_code == 403


def test_read_item_requires_auth(client):
    assert client.get("/items/1").status_code == 401


# ---------------------------------------------------------------------------
# DELETE /items/{id}
# ---------------------------------------------------------------------------

def test_delete_item(auth_headers):
    client, _ = auth_headers
    item_id = client.post("/items/", params={"name": "Delete me now"}).json()["id"]
    assert client.delete(f"/items/{item_id}").json() == {"ok": True}
    assert client.get(f"/items/{item_id}").status_code == 404


def test_delete_item_not_found(auth_headers):
    client, _ = auth_headers
    assert client.delete("/items/9999").status_code == 404


def test_delete_item_wrong_owner_is_forbidden(auth_headers, session):
    client, _ = auth_headers
    other = create_user(session, username="otheruser4", password="password1234")
    item = Item(name="Other persons item", creator_id=other.id)
    session.add(item)
    session.commit()
    session.refresh(item)
    assert client.delete(f"/items/{item.id}").status_code == 403


def test_delete_item_requires_auth(client):
    assert client.delete("/items/1").status_code == 401


# ---------------------------------------------------------------------------
# POST /items/{id}/reorder
# ---------------------------------------------------------------------------

def _create_items(client, *names) -> list[int]:
    """Helper: create multiple items and return their ids in creation order."""
    return [client.post("/items/", params={"name": name}).json()["id"] for name in names]


def _order_keys(client, ids) -> list[str]:
    """Helper: return order_keys for a list of item ids after reordering each to end."""
    return [client.post(f"/items/{id}/reorder", json={"after_id": None}).json()["order_key"] for id in ids]


def test_reorder_returns_order_key(auth_headers):
    client, _ = auth_headers
    a, b = _create_items(client, "Item alpha aa", "Item beta bbb")
    response = client.post(f"/items/{b}/reorder", json={"after_id": a})
    assert response.status_code == 200
    assert "order_key" in response.json()


def test_reorder_move_to_front(auth_headers, session):
    client, user = auth_headers
    a, b, c = _create_items(client, "Item alpha aa", "Item beta bbb", "Item gamma cc")

    # Move c to front (after_id=None)
    client.post(f"/items/{c}/reorder", json={"after_id": None})

    from db.item_orders import get_user_order
    ordered_ids = [o.item_id for o in get_user_order(session, user.id)]
    assert ordered_ids.index(c) < ordered_ids.index(a)
    assert ordered_ids.index(c) < ordered_ids.index(b)


def test_reorder_move_to_middle(auth_headers, session):
    client, user = auth_headers
    a, b, c = _create_items(client, "Item alpha aa", "Item beta bbb", "Item gamma cc")

    # Natural order after creation: a, b, c
    # Move c after a → expected: a, c, b
    client.post(f"/items/{c}/reorder", json={"after_id": a})

    from db.item_orders import get_user_order
    ordered_ids = [o.item_id for o in get_user_order(session, user.id)]
    assert ordered_ids.index(a) < ordered_ids.index(c) < ordered_ids.index(b)


def test_reorder_move_to_end(auth_headers, session):
    client, user = auth_headers
    a, b, c = _create_items(client, "Item alpha aa", "Item beta bbb", "Item gamma cc")

    # Move a to end (after c)
    client.post(f"/items/{a}/reorder", json={"after_id": c})

    from db.item_orders import get_user_order
    ordered_ids = [o.item_id for o in get_user_order(session, user.id)]
    assert ordered_ids[-1] == a


def test_reorder_keys_remain_sortable(auth_headers):
    client, _ = auth_headers
    a, b, c = _create_items(client, "Item alpha aa", "Item beta bbb", "Item gamma cc")

    # Move b to front, then c after a
    key_b = client.post(f"/items/{b}/reorder", json={"after_id": None}).json()["order_key"]
    key_a = client.post(f"/items/{a}/reorder", json={"after_id": b}).json()["order_key"]
    key_c = client.post(f"/items/{c}/reorder", json={"after_id": a}).json()["order_key"]

    assert key_b < key_a < key_c


def test_reorder_item_not_found(auth_headers):
    client, _ = auth_headers
    assert client.post("/items/9999/reorder", json={"after_id": None}).status_code == 404


def test_reorder_after_id_not_found(auth_headers):
    client, _ = auth_headers
    item_id = client.post("/items/", params={"name": "Some item here"}).json()["id"]
    assert client.post(f"/items/{item_id}/reorder", json={"after_id": 9999}).status_code == 404


def test_reorder_wrong_owner_is_forbidden(auth_headers, session):
    client, _ = auth_headers
    other = create_user(session, username="otheruser5", password="password1234")
    item = Item(name="Not your item!!", creator_id=other.id)
    session.add(item)
    session.commit()
    session.refresh(item)
    assert client.post(f"/items/{item.id}/reorder", json={"after_id": None}).status_code == 403


def test_reorder_after_id_wrong_owner_is_forbidden(auth_headers, session):
    client, _ = auth_headers
    other = create_user(session, username="otheruser6", password="password1234")
    other_item = Item(name="Belongs to other!!", creator_id=other.id)
    session.add(other_item)
    session.commit()
    session.refresh(other_item)

    my_item_id = client.post("/items/", params={"name": "My own item aa"}).json()["id"]
    assert client.post(f"/items/{my_item_id}/reorder", json={"after_id": other_item.id}).status_code == 403


def test_reorder_requires_auth(client):
    assert client.post("/items/1/reorder", json={"after_id": None}).status_code == 401


# ---------------------------------------------------------------------------
# GET /items/?sort_by=...
# ---------------------------------------------------------------------------

def test_sort_by_default_returns_items(auth_headers):
    client, _ = auth_headers
    _create_items(client, "First item aaa", "Second item bb")
    assert client.get("/items/").status_code == 200


def test_sort_by_invalid_value_rejected(auth_headers):
    client, _ = auth_headers
    assert client.get("/items/", params={"sort_by": "invalid"}).status_code == 422


def test_sort_by_created_on(auth_headers):
    client, _ = auth_headers
    ids = _create_items(client, "First item aaa", "Second item bb", "Third item cc")
    response = client.get("/items/", params={"sort_by": "created_on", "size": 100})
    assert response.status_code == 200
    assert [i["id"] for i in response.json()["items"]] == ids


def test_sort_by_priority(auth_headers, session):
    client, user = auth_headers
    high = Item(name="High priority item", creator_id=user.id, priority=Priority.HIGH)
    med  = Item(name="Med priority item!", creator_id=user.id, priority=Priority.MEDIUM)
    low  = Item(name="Low priority item!", creator_id=user.id, priority=Priority.LOW)
    session.add_all([low, med, high])  # add out of order
    session.commit()
    for item in [low, med, high]:
        session.refresh(item)

    response = client.get("/items/", params={"sort_by": "priority", "size": 100})
    assert response.status_code == 200
    ids = [i["id"] for i in response.json()["items"]]
    # Priority is stored as an integer (HIGH=0, MEDIUM=1, LOW=2), so ORDER BY
    # sorts numerically: HIGH(0) < MEDIUM(1) < LOW(2)
    assert ids == [high.id, med.id, low.id]


def test_sort_by_due_on(auth_headers, session):
    client, user = auth_headers
    now = dt.datetime.now(dt.timezone.utc)
    first  = Item(name="Due first item aa", creator_id=user.id, due_on=now + dt.timedelta(days=1))
    second = Item(name="Due second itembb", creator_id=user.id, due_on=now + dt.timedelta(days=2))
    third  = Item(name="Due third item cc", creator_id=user.id, due_on=now + dt.timedelta(days=3))
    session.add_all([third, first, second])  # add out of order
    session.commit()
    for item in [third, first, second]:
        session.refresh(item)

    response = client.get("/items/", params={"sort_by": "due_on", "size": 100})
    assert response.status_code == 200
    ids = [i["id"] for i in response.json()["items"]]
    assert ids == [first.id, second.id, third.id]


def test_sort_by_custom(auth_headers):
    client, _ = auth_headers
    a, b, c = _create_items(client, "Item alpha aa", "Item beta bbb", "Item gamma cc")

    # Reorder to: b, c, a
    client.post(f"/items/{b}/reorder", json={"after_id": None})
    client.post(f"/items/{c}/reorder", json={"after_id": b})
    client.post(f"/items/{a}/reorder", json={"after_id": c})

    response = client.get("/items/", params={"sort_by": "custom", "size": 100})
    assert response.status_code == 200
    assert [i["id"] for i in response.json()["items"]] == [b, c, a]


def test_sort_by_custom_unordered_items_still_returned(auth_headers):
    """Items with no UserItemOrder entry still appear when sort_by=custom."""
    client, _ = auth_headers
    ids = _create_items(client, "Item alpha aa", "Item beta bbb")
    response = client.get("/items/", params={"sort_by": "custom", "size": 100})
    assert response.status_code == 200
    assert set(i["id"] for i in response.json()["items"]) == set(ids)


# ---------------------------------------------------------------------------
# GET /items/?reverse=true
# ---------------------------------------------------------------------------

def test_reverse_created_on(auth_headers):
    client, _ = auth_headers
    ids = _create_items(client, "First item aaa", "Second item bb", "Third item cc")
    response = client.get("/items/", params={"sort_by": "created_on", "reverse": "true", "size": 100})
    assert response.status_code == 200
    assert [i["id"] for i in response.json()["items"]] == list(reversed(ids))


def test_reverse_priority(auth_headers, session):
    client, user = auth_headers
    high = Item(name="High priority item", creator_id=user.id, priority=Priority.HIGH)
    med  = Item(name="Med priority item!", creator_id=user.id, priority=Priority.MEDIUM)
    low  = Item(name="Low priority item!", creator_id=user.id, priority=Priority.LOW)
    session.add_all([low, med, high])
    session.commit()
    for item in [low, med, high]:
        session.refresh(item)

    response = client.get("/items/", params={"sort_by": "priority", "reverse": "true", "size": 100})
    assert response.status_code == 200
    ids = [i["id"] for i in response.json()["items"]]
    assert ids == [low.id, med.id, high.id]


def test_reverse_custom(auth_headers):
    client, _ = auth_headers
    a, b, c = _create_items(client, "Item alpha aa", "Item beta bbb", "Item gamma cc")

    # Order: b, c, a — reversed should be a, c, b
    client.post(f"/items/{b}/reorder", json={"after_id": None})
    client.post(f"/items/{c}/reorder", json={"after_id": b})
    client.post(f"/items/{a}/reorder", json={"after_id": c})

    response = client.get("/items/", params={"sort_by": "custom", "reverse": "true", "size": 100})
    assert response.status_code == 200
    assert [i["id"] for i in response.json()["items"]] == [a, c, b]


# ---------------------------------------------------------------------------
# PATCH /items/{id}
# ---------------------------------------------------------------------------

def test_patch_item_name(auth_headers):
    client, _ = auth_headers
    item_id = client.post("/items/", params={"name": "Original name aa"}).json()["id"]
    response = client.patch(f"/items/{item_id}", json={"name": "Updated name aa"})
    assert response.status_code == 200
    assert response.json()["name"] == "Updated name aa"


def test_patch_item_description(auth_headers):
    client, _ = auth_headers
    item_id = client.post("/items/", params={"name": "Some item namebb"}).json()["id"]
    response = client.patch(f"/items/{item_id}", json={"description": "A new description"})
    assert response.status_code == 200
    assert response.json()["description"] == "A new description"


def test_patch_item_priority(auth_headers):
    client, _ = auth_headers
    item_id = client.post("/items/", params={"name": "Some item namecc"}).json()["id"]
    response = client.patch(f"/items/{item_id}", json={"priority": Priority.HIGH})
    assert response.status_code == 200
    assert response.json()["priority"] == Priority.HIGH


def test_patch_item_due_on(auth_headers):
    client, _ = auth_headers
    item_id = client.post("/items/", params={"name": "Some item namedd"}).json()["id"]
    due = "2026-06-01T12:00:00Z"
    response = client.patch(f"/items/{item_id}", json={"due_on": due})
    assert response.status_code == 200
    assert response.json()["due_on"] is not None


def test_patch_item_multiple_fields(auth_headers):
    client, _ = auth_headers
    item_id = client.post("/items/", params={"name": "Multi field itemee"}).json()["id"]
    response = client.patch(f"/items/{item_id}", json={
        "name": "Updated multi itemee",
        "description": "Updated desc",
        "priority": Priority.LOW,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated multi itemee"
    assert data["description"] == "Updated desc"
    assert data["priority"] == Priority.LOW


def test_patch_item_only_updates_given_fields(auth_headers):
    """Fields omitted from the body must not be changed."""
    client, _ = auth_headers
    item_id = client.post("/items/", params={"name": "Stable name itemff", "description": "Keep this"}).json()["id"]
    client.patch(f"/items/{item_id}", json={"priority": Priority.HIGH})
    data = client.get(f"/items/{item_id}").json()
    assert data["description"] == "Keep this"


def test_patch_item_clears_nullable_field(auth_headers):
    """Explicitly passing null for a nullable field should clear it."""
    client, _ = auth_headers
    item_id = client.post("/items/", params={"name": "Has description gg", "description": "To be cleared"}).json()["id"]
    client.patch(f"/items/{item_id}", json={"description": None})
    data = client.get(f"/items/{item_id}").json()
    assert data["description"] is None


def test_patch_item_name_too_short(auth_headers):
    client, _ = auth_headers
    item_id = client.post("/items/", params={"name": "Valid name itemhh"}).json()["id"]
    assert client.patch(f"/items/{item_id}", json={"name": "short"}).status_code == 422


def test_patch_item_not_found(auth_headers):
    client, _ = auth_headers
    assert client.patch("/items/9999", json={"name": "Does not matter!"}).status_code == 404


def test_patch_item_wrong_owner_is_forbidden(auth_headers, session):
    client, _ = auth_headers
    other = create_user(session, username="otheruser7", password="password1234")
    item = Item(name="Belongs to other!!", creator_id=other.id)
    session.add(item)
    session.commit()
    session.refresh(item)
    assert client.patch(f"/items/{item.id}", json={"name": "Trying to steal!"}).status_code == 403


def test_patch_item_requires_auth(client):
    assert client.patch("/items/1", json={"name": "No auth attempt!"}).status_code == 401
