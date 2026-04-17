import datetime as dt

from sqlmodel import Session

from constants import Priority, State
from db.models import Item, ItemOwnership, Tag, ItemTag
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
    session.flush()
    session.add(ItemOwnership(item_id=item.id, user_id=other.id))
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
    session.flush()
    session.add(ItemOwnership(item_id=item.id, user_id=other.id))
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
    session.flush()
    session.add(ItemOwnership(item_id=item.id, user_id=other.id))
    session.commit()
    session.refresh(item)
    assert client.post(f"/items/{item.id}/reorder", json={"after_id": None}).status_code == 403


def test_reorder_after_id_wrong_owner_is_forbidden(auth_headers, session):
    client, _ = auth_headers
    other = create_user(session, username="otheruser6", password="password1234")
    other_item = Item(name="Belongs to other!!", creator_id=other.id)
    session.add(other_item)
    session.flush()
    session.add(ItemOwnership(item_id=other_item.id, user_id=other.id))
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
    session.flush()
    for item in [low, med, high]:
        session.add(ItemOwnership(item_id=item.id, user_id=user.id))
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
    session.flush()
    for item in [third, first, second]:
        session.add(ItemOwnership(item_id=item.id, user_id=user.id))
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
    session.flush()
    for item in [low, med, high]:
        session.add(ItemOwnership(item_id=item.id, user_id=user.id))
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
    session.flush()
    session.add(ItemOwnership(item_id=item.id, user_id=other.id))
    session.commit()
    session.refresh(item)
    assert client.patch(f"/items/{item.id}", json={"name": "Trying to steal!"}).status_code == 403


def test_patch_item_requires_auth(client):
    assert client.patch("/items/1", json={"name": "No auth attempt!"}).status_code == 401


# ---------------------------------------------------------------------------
# State field
# ---------------------------------------------------------------------------

def test_new_item_has_new_state(auth_headers):
    client, _ = auth_headers
    item_id = client.post("/items/", params={"name": "Check default state!"}).json()["id"]
    data = client.get(f"/items/{item_id}").json()
    assert data["state"] == State.NEW


def test_patch_item_state(auth_headers):
    client, _ = auth_headers
    item_id = client.post("/items/", params={"name": "Change state itemaa"}).json()["id"]
    response = client.patch(f"/items/{item_id}", json={"state": State.IN_PROGRESS})
    assert response.status_code == 200
    assert response.json()["state"] == State.IN_PROGRESS


def test_patch_item_state_all_values(auth_headers):
    client, _ = auth_headers
    item_id = client.post("/items/", params={"name": "All states item bb"}).json()["id"]
    for state in State:
        response = client.patch(f"/items/{item_id}", json={"state": state})
        assert response.status_code == 200
        assert response.json()["state"] == state


# ---------------------------------------------------------------------------
# completed_on auto-management
# ---------------------------------------------------------------------------

def test_new_item_has_no_completed_on(auth_headers):
    client, _ = auth_headers
    item_id = client.post("/items/", params={"name": "No completed on yet!"}).json()["id"]
    data = client.get(f"/items/{item_id}").json()
    assert data["completed_on"] is None


def test_patch_state_to_done_sets_completed_on(auth_headers):
    client, _ = auth_headers
    item_id = client.post("/items/", params={"name": "Done state test item"}).json()["id"]
    response = client.patch(f"/items/{item_id}", json={"state": State.DONE})
    assert response.status_code == 200
    assert response.json()["completed_on"] is not None


def test_patch_state_to_cancelled_sets_completed_on(auth_headers):
    client, _ = auth_headers
    item_id = client.post("/items/", params={"name": "Cancelled state test!"}).json()["id"]
    response = client.patch(f"/items/{item_id}", json={"state": State.CANCELLED})
    assert response.status_code == 200
    assert response.json()["completed_on"] is not None


def test_patch_state_to_in_progress_clears_completed_on(auth_headers):
    client, _ = auth_headers
    item_id = client.post("/items/", params={"name": "In progress clears it"}).json()["id"]
    client.patch(f"/items/{item_id}", json={"state": State.DONE})
    response = client.patch(f"/items/{item_id}", json={"state": State.IN_PROGRESS})
    assert response.status_code == 200
    assert response.json()["completed_on"] is None


def test_patch_state_to_new_clears_completed_on(auth_headers):
    client, _ = auth_headers
    item_id = client.post("/items/", params={"name": "New state clears itaa"}).json()["id"]
    client.patch(f"/items/{item_id}", json={"state": State.CANCELLED})
    response = client.patch(f"/items/{item_id}", json={"state": State.NEW})
    assert response.status_code == 200
    assert response.json()["completed_on"] is None


def test_recompletion_resets_completed_on(auth_headers):
    client, _ = auth_headers
    item_id = client.post("/items/", params={"name": "Recompletion test aaa"}).json()["id"]
    first_ts = client.patch(f"/items/{item_id}", json={"state": State.DONE}).json()["completed_on"]
    client.patch(f"/items/{item_id}", json={"state": State.NEW})
    response = client.patch(f"/items/{item_id}", json={"state": State.DONE})
    assert response.status_code == 200
    assert response.json()["completed_on"] is not None


def test_patch_non_state_field_does_not_change_completed_on(auth_headers):
    client, _ = auth_headers
    item_id = client.post("/items/", params={"name": "Non state field test"}).json()["id"]
    completed_on = client.patch(f"/items/{item_id}", json={"state": State.DONE}).json()["completed_on"]
    client.patch(f"/items/{item_id}", json={"name": "Non state field tst2"})
    data = client.get(f"/items/{item_id}").json()
    assert data["completed_on"] == completed_on


# ---------------------------------------------------------------------------
# completed_by_id auto-management
# ---------------------------------------------------------------------------

def test_new_item_has_no_completed_by(auth_headers):
    client, _ = auth_headers
    item_id = client.post("/items/", params={"name": "No completed by yet!"}).json()["id"]
    data = client.get(f"/items/{item_id}").json()
    assert data["completed_by_id"] is None


def test_patch_state_to_done_sets_completed_by(auth_headers):
    client, user = auth_headers
    item_id = client.post("/items/", params={"name": "Done sets completed by!"}).json()["id"]
    response = client.patch(f"/items/{item_id}", json={"state": State.DONE})
    assert response.status_code == 200
    assert response.json()["completed_by_id"] == user.id


def test_patch_state_to_cancelled_sets_completed_by(auth_headers):
    client, user = auth_headers
    item_id = client.post("/items/", params={"name": "Cancelled completed by!"}).json()["id"]
    response = client.patch(f"/items/{item_id}", json={"state": State.CANCELLED})
    assert response.status_code == 200
    assert response.json()["completed_by_id"] == user.id


def test_patch_state_to_in_progress_clears_completed_by(auth_headers):
    client, _ = auth_headers
    item_id = client.post("/items/", params={"name": "IP clears completed by!"}).json()["id"]
    client.patch(f"/items/{item_id}", json={"state": State.DONE})
    response = client.patch(f"/items/{item_id}", json={"state": State.IN_PROGRESS})
    assert response.status_code == 200
    assert response.json()["completed_by_id"] is None


def test_patch_state_to_new_clears_completed_by(auth_headers):
    client, _ = auth_headers
    item_id = client.post("/items/", params={"name": "New clears completed by!"}).json()["id"]
    client.patch(f"/items/{item_id}", json={"state": State.CANCELLED})
    response = client.patch(f"/items/{item_id}", json={"state": State.NEW})
    assert response.status_code == 200
    assert response.json()["completed_by_id"] is None


def test_patch_non_state_field_does_not_change_completed_by(auth_headers):
    client, user = auth_headers
    item_id = client.post("/items/", params={"name": "No state no by change!!"}).json()["id"]
    client.patch(f"/items/{item_id}", json={"state": State.DONE})
    client.patch(f"/items/{item_id}", json={"name": "No state no by change!a"})
    data = client.get(f"/items/{item_id}").json()
    assert data["completed_by_id"] == user.id


def test_sort_by_state(auth_headers, session):
    client, user = auth_headers
    done      = Item(name="Done item aaaaaaaa", creator_id=user.id, state=State.DONE)
    new       = Item(name="New item aaaaaaaaa", creator_id=user.id, state=State.NEW)
    cancelled = Item(name="Cancelled item aaa", creator_id=user.id, state=State.CANCELLED)
    in_prog   = Item(name="In progress itemaa", creator_id=user.id, state=State.IN_PROGRESS)
    session.add_all([done, cancelled, in_prog, new])
    session.flush()
    for item in [done, cancelled, in_prog, new]:
        session.add(ItemOwnership(item_id=item.id, user_id=user.id))
    session.commit()
    for item in [done, new, cancelled, in_prog]:
        session.refresh(item)

    response = client.get("/items/", params={"sort_by": "state", "size": 100})
    assert response.status_code == 200
    ids = [i["id"] for i in response.json()["items"]]
    assert ids == [new.id, in_prog.id, done.id, cancelled.id]


# ---------------------------------------------------------------------------
# POST /items/search
# ---------------------------------------------------------------------------

def _search(client, **filter_fields):
    """Helper: POST /items/search with the given filter fields, size=100."""
    return client.post("/items/search", json=filter_fields, params={"size": 100})


def test_search_empty_filter_returns_all(auth_headers):
    client, _ = auth_headers
    client.post("/items/", params={"name": "Search item one aaa"})
    client.post("/items/", params={"name": "Search item two aaa"})
    response = _search(client)
    assert response.status_code == 200
    names = [i["name"] for i in response.json()["items"]]
    assert "Search item one aaa" in names
    assert "Search item two aaa" in names


def test_search_requires_auth(client):
    assert client.post("/items/search", json={}).status_code == 401


def test_search_filter_by_name_substring(auth_headers):
    client, _ = auth_headers
    client.post("/items/", params={"name": "Fix the login bug"})
    client.post("/items/", params={"name": "Write release notes"})
    ids = [i["id"] for i in _search(client, name="login").json()["items"]]
    assert len(ids) == 1


def test_search_filter_by_name_case_insensitive(auth_headers):
    client, _ = auth_headers
    client.post("/items/", params={"name": "Fix the LOGIN bug"})
    ids = [i["id"] for i in _search(client, name="login").json()["items"]]
    assert len(ids) == 1


def test_search_filter_by_name_no_match(auth_headers):
    client, _ = auth_headers
    client.post("/items/", params={"name": "Nothing matches here"})
    items = _search(client, name="xyzzy").json()["items"]
    assert items == []


def test_search_filter_by_single_state(auth_headers):
    client, _ = auth_headers
    id_new  = client.post("/items/", params={"name": "State filter new aaa"}).json()["id"]
    id_done = client.post("/items/", params={"name": "State filter done aa"}).json()["id"]
    client.patch(f"/items/{id_done}", json={"state": State.DONE})
    ids = [i["id"] for i in _search(client, state=[State.DONE]).json()["items"]]
    assert id_done in ids
    assert id_new not in ids


def test_search_filter_by_multiple_states(auth_headers):
    client, _ = auth_headers
    id_new  = client.post("/items/", params={"name": "Multi state new aaaa"}).json()["id"]
    id_prog = client.post("/items/", params={"name": "Multi state prog aaa"}).json()["id"]
    id_done = client.post("/items/", params={"name": "Multi state done aaa"}).json()["id"]
    client.patch(f"/items/{id_prog}", json={"state": State.IN_PROGRESS})
    client.patch(f"/items/{id_done}", json={"state": State.DONE})
    ids = [i["id"] for i in _search(client, state=[State.NEW, State.IN_PROGRESS]).json()["items"]]
    assert id_new in ids
    assert id_prog in ids
    assert id_done not in ids


def test_search_filter_by_priority(auth_headers):
    client, _ = auth_headers
    id_high = client.post("/items/", params={"name": "Priority high item!"}).json()["id"]
    id_low  = client.post("/items/", params={"name": "Priority low itemaa"}).json()["id"]
    client.patch(f"/items/{id_high}", json={"priority": Priority.HIGH})
    client.patch(f"/items/{id_low}",  json={"priority": Priority.LOW})
    ids = [i["id"] for i in _search(client, priority=[Priority.HIGH]).json()["items"]]
    assert id_high in ids
    assert id_low not in ids


def test_search_filter_by_multiple_priorities(auth_headers):
    client, _ = auth_headers
    id_high   = client.post("/items/", params={"name": "Multi prio high aaa"}).json()["id"]
    id_medium = client.post("/items/", params={"name": "Multi prio medium aa"}).json()["id"]
    id_low    = client.post("/items/", params={"name": "Multi prio low aaaaa"}).json()["id"]
    client.patch(f"/items/{id_high}",   json={"priority": Priority.HIGH})
    client.patch(f"/items/{id_medium}", json={"priority": Priority.MEDIUM})
    client.patch(f"/items/{id_low}",    json={"priority": Priority.LOW})
    ids = [i["id"] for i in _search(client, priority=[Priority.HIGH, Priority.LOW]).json()["items"]]
    assert id_high in ids
    assert id_low in ids
    assert id_medium not in ids


def test_search_filter_by_created_after(auth_headers, session):
    client, user = auth_headers
    old = Item(
        name="Old item aaaaaaaa", creator_id=user.id,
        created_on=dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc),
    )
    new = Item(
        name="New item aaaaaaaa", creator_id=user.id,
        created_on=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
    )
    session.add_all([old, new])
    session.flush()
    for item in [old, new]:
        session.add(ItemOwnership(item_id=item.id, user_id=user.id))
    session.commit()
    threshold = "2023-01-01T00:00:00Z"
    ids = [i["id"] for i in _search(client, created_after=threshold).json()["items"]]
    assert new.id in ids
    assert old.id not in ids


def test_search_filter_by_created_before(auth_headers, session):
    client, user = auth_headers
    old = Item(
        name="Old created item aa", creator_id=user.id,
        created_on=dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc),
    )
    new = Item(
        name="New created item aa", creator_id=user.id,
        created_on=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
    )
    session.add_all([old, new])
    session.flush()
    for item in [old, new]:
        session.add(ItemOwnership(item_id=item.id, user_id=user.id))
    session.commit()
    threshold = "2023-01-01T00:00:00Z"
    ids = [i["id"] for i in _search(client, created_before=threshold).json()["items"]]
    assert old.id in ids
    assert new.id not in ids


def test_search_filter_by_created_on(auth_headers, session):
    client, user = auth_headers
    target_day = dt.datetime(2025, 6, 15, 12, 0, tzinfo=dt.timezone.utc)
    other_day  = dt.datetime(2025, 6, 16, 12, 0, tzinfo=dt.timezone.utc)
    match = Item(name="Created on target day", creator_id=user.id, created_on=target_day)
    no_match = Item(name="Created on other day!", creator_id=user.id, created_on=other_day)
    session.add_all([match, no_match])
    session.flush()
    for item in [match, no_match]:
        session.add(ItemOwnership(item_id=item.id, user_id=user.id))
    session.commit()
    ids = [i["id"] for i in _search(client, created_on="2025-06-15").json()["items"]]
    assert match.id in ids
    assert no_match.id not in ids


def test_search_filter_by_due_on(auth_headers, session):
    client, user = auth_headers
    target = dt.datetime(2025, 9, 1, 9, 0, tzinfo=dt.timezone.utc)
    other  = dt.datetime(2025, 9, 2, 9, 0, tzinfo=dt.timezone.utc)
    match    = Item(name="Due on target day aaa", creator_id=user.id, due_on=target)
    no_match = Item(name="Due on other day aaaa", creator_id=user.id, due_on=other)
    session.add_all([match, no_match])
    session.flush()
    for item in [match, no_match]:
        session.add(ItemOwnership(item_id=item.id, user_id=user.id))
    session.commit()
    ids = [i["id"] for i in _search(client, due_on="2025-09-01").json()["items"]]
    assert match.id in ids
    assert no_match.id not in ids


def test_search_filter_by_completed_on(auth_headers, session):
    client, user = auth_headers
    target = dt.datetime(2025, 3, 10, 15, 0, tzinfo=dt.timezone.utc)
    other  = dt.datetime(2025, 3, 11, 15, 0, tzinfo=dt.timezone.utc)
    match    = Item(name="Completed on target!!", creator_id=user.id, completed_on=target, state=State.DONE)
    no_match = Item(name="Completed on other day", creator_id=user.id, completed_on=other, state=State.DONE)
    session.add_all([match, no_match])
    session.flush()
    for item in [match, no_match]:
        session.add(ItemOwnership(item_id=item.id, user_id=user.id))
    session.commit()
    ids = [i["id"] for i in _search(client, completed_on="2025-03-10").json()["items"]]
    assert match.id in ids
    assert no_match.id not in ids


def test_search_filter_by_single_tag(auth_headers, session):
    client, user = auth_headers
    tagged   = Item(name="Tagged item aaaaaaaa", creator_id=user.id)
    untagged = Item(name="Untagged item aaaaaa", creator_id=user.id)
    tag = Tag(name="urgent")
    session.add_all([tagged, untagged, tag])
    session.flush()
    for item in [tagged, untagged]:
        session.add(ItemOwnership(item_id=item.id, user_id=user.id))
    session.commit()
    session.add(ItemTag(item_id=tagged.id, tag_id=tag.id))
    session.commit()
    ids = [i["id"] for i in _search(client, tags=["urgent"]).json()["items"]]
    assert tagged.id in ids
    assert untagged.id not in ids


def test_search_filter_by_multiple_tags_or_semantics(auth_headers, session):
    client, user = auth_headers
    item_a  = Item(name="Item with tag work aa", creator_id=user.id)
    item_b  = Item(name="Item with tag urgent!", creator_id=user.id)
    item_ab = Item(name="Item with both tags!!", creator_id=user.id)
    item_c  = Item(name="Item with no tags aaa", creator_id=user.id)
    tag_w = Tag(name="work")
    tag_u = Tag(name="urgent2")
    session.add_all([item_a, item_b, item_ab, item_c, tag_w, tag_u])
    session.flush()
    for item in [item_a, item_b, item_ab, item_c]:
        session.add(ItemOwnership(item_id=item.id, user_id=user.id))
    session.commit()
    session.add_all([
        ItemTag(item_id=item_a.id,  tag_id=tag_w.id),
        ItemTag(item_id=item_b.id,  tag_id=tag_u.id),
        ItemTag(item_id=item_ab.id, tag_id=tag_w.id),
        ItemTag(item_id=item_ab.id, tag_id=tag_u.id),
    ])
    session.commit()
    ids = [i["id"] for i in _search(client, tags=["work", "urgent2"]).json()["items"]]
    assert item_a.id in ids
    assert item_b.id in ids
    assert item_ab.id in ids
    assert item_c.id not in ids


def test_search_filter_combined(auth_headers, session):
    client, user = auth_headers
    tag = Tag(name="combined-tag")
    session.add(tag)
    session.commit()

    match = Item(name="Combined match item!", creator_id=user.id, state=State.DONE)
    wrong_state = Item(name="Combined match item!", creator_id=user.id, state=State.NEW)
    wrong_name  = Item(name="No match at all aaaa", creator_id=user.id, state=State.DONE)
    no_tag      = Item(name="Combined match item!", creator_id=user.id, state=State.DONE)
    session.add_all([match, wrong_state, wrong_name, no_tag])
    session.flush()
    for item in [match, wrong_state, wrong_name, no_tag]:
        session.add(ItemOwnership(item_id=item.id, user_id=user.id))
    session.commit()
    session.add(ItemTag(item_id=match.id, tag_id=tag.id))
    session.add(ItemTag(item_id=wrong_state.id, tag_id=tag.id))
    session.add(ItemTag(item_id=wrong_name.id, tag_id=tag.id))
    session.commit()

    ids = [i["id"] for i in _search(
        client, name="Combined", state=[State.DONE], tags=["combined-tag"]
    ).json()["items"]]
    assert match.id in ids
    assert wrong_state.id not in ids
    assert wrong_name.id not in ids
    assert no_tag.id not in ids


def test_search_no_cross_user_leakage(auth_headers, session):
    client, _ = auth_headers
    other = create_user(session, username="otheruser3", password="password1234")
    session.add(Item(name="Other users item aaa", creator_id=other.id))
    session.commit()
    names = [i["name"] for i in _search(client).json()["items"]]
    assert "Other users item aaa" not in names


# ---------------------------------------------------------------------------
# POST /items/{id}/assign/user/{username}
# POST /items/{id}/assign/group/{group_id}
# ---------------------------------------------------------------------------

from constants import FriendshipStatus
from db import friendships as db_friends
from db import groups as db_groups
from db.users import get_by_username
from util.security import encode_token


def _make_friend(session, user, username="frienduser1"):
    """Create a user and establish an ACCEPTED friendship with user."""
    friend = create_user(session, username=username, password="password1234")
    friendship = db_friends.request(session, user.id, friend.id)
    db_friends.accept(session, friendship)
    return friend


def _make_friend_client(session, friend):
    """Return an authenticated TestClient for friend."""
    from fastapi.testclient import TestClient as TC
    from app.main import app
    from db.main import get_session
    token = encode_token({"sub": friend.username})
    app.dependency_overrides[get_session] = lambda: session
    return TC(app, raise_server_exceptions=True,
              headers={"Authorization": f"Bearer {token}"})


def test_assign_to_self(auth_headers):
    client, _ = auth_headers
    item_id = client.post("/items/", params={"name": "Assign to self item"}).json()["id"]
    response = client.post(f"/items/{item_id}/assign/user/testuser1")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_assign_to_friend(auth_headers, session):
    client, user = auth_headers
    friend = _make_friend(session, user, "frienduser2")
    item_id = client.post("/items/", params={"name": "Assign to friend item"}).json()["id"]
    response = client.post(f"/items/{item_id}/assign/user/{friend.username}")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_assign_to_non_friend_returns_403(auth_headers, session):
    client, _ = auth_headers
    stranger = create_user(session, username="strangeruser1", password="password1234")
    item_id = client.post("/items/", params={"name": "Assign to stranger!"}).json()["id"]
    response = client.post(f"/items/{item_id}/assign/user/{stranger.username}")
    assert response.status_code == 403


def test_assign_non_owner_returns_403(auth_headers, session):
    """A user who is not the current owner cannot transfer ownership."""
    client, user = auth_headers
    friend = _make_friend(session, user, "frienduser3")
    friend_client = _make_friend_client(session, friend)

    # friend creates their own item; testuser1 is not the owner and cannot reassign it
    friend_item_id = friend_client.post("/items/", params={"name": "Friends own item aa"}).json()["id"]
    response = client.post(f"/items/{friend_item_id}/assign/user/testuser1")
    assert response.status_code == 403


def test_assign_item_not_found_returns_404(auth_headers):
    client, _ = auth_headers
    assert client.post("/items/9999/assign/user/testuser1").status_code == 404


def test_assign_user_not_found_returns_404(auth_headers):
    client, _ = auth_headers
    item_id = client.post("/items/", params={"name": "Assign user 404 test"}).json()["id"]
    assert client.post(f"/items/{item_id}/assign/user/nosuchuser123").status_code == 404


def test_assigned_item_visible_to_assignee(auth_headers, session):
    client, user = auth_headers
    friend = _make_friend(session, user, "frienduser4")
    friend_client = _make_friend_client(session, friend)

    item_id = client.post("/items/", params={"name": "Visible to assignee!"}).json()["id"]
    client.post(f"/items/{item_id}/assign/user/{friend.username}")

    names = [i["name"] for i in friend_client.get("/items/", params={"size": 100}).json()["items"]]
    assert "Visible to assignee!" in names


def test_creator_can_still_see_item_after_reassignment(auth_headers, session):
    """Creator retains read visibility even after ownership is transferred to a friend."""
    client, user = auth_headers
    friend = _make_friend(session, user, "frienduser5")

    item_id = client.post("/items/", params={"name": "Stays visible to creator"}).json()["id"]
    client.post(f"/items/{item_id}/assign/user/{friend.username}")

    names = [i["name"] for i in client.get("/items/", params={"size": 100}).json()["items"]]
    assert "Stays visible to creator" in names


def test_assign_to_group_as_member(auth_headers, session):
    """Setting a group preserves user_id — owner retains ownership."""
    client, user = auth_headers
    group = db_groups.create(session, name="Test group", owner_id=user.id)
    item_id = client.post("/items/", params={"name": "Assign to group item"}).json()["id"]
    response = client.post(f"/items/{item_id}/assign/group/{group.id}")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    # Owner still owns the item (user_id not cleared)
    from db.models import ItemOwnership as IO
    ownership = session.get(IO, item_id)
    assert ownership.user_id == user.id
    assert ownership.group_id == group.id


def test_assign_to_group_not_member_returns_403(auth_headers, session):
    client, user = auth_headers
    other = create_user(session, username="groupowner11", password="password1234")
    group = db_groups.create(session, name="Others group", owner_id=other.id)
    item_id = client.post("/items/", params={"name": "Assign to other grp!"}).json()["id"]
    response = client.post(f"/items/{item_id}/assign/group/{group.id}")
    assert response.status_code == 403


def test_assign_to_group_not_found_returns_404(auth_headers):
    client, _ = auth_headers
    item_id = client.post("/items/", params={"name": "Assign group 404 tst"}).json()["id"]
    assert client.post(f"/items/{item_id}/assign/group/9999").status_code == 404


def test_group_assigned_item_visible_to_members(auth_headers, session):
    client, user = auth_headers
    friend = _make_friend(session, user, "frienduser6")
    group = db_groups.create(session, name="Shared group", owner_id=user.id)
    db_groups.add_member(session, group.id, friend.id)

    item_id = client.post("/items/", params={"name": "Group visible item!!"}).json()["id"]
    client.post(f"/items/{item_id}/assign/group/{group.id}")

    friend_client = _make_friend_client(session, friend)
    names = [i["name"] for i in friend_client.get("/items/", params={"size": 100}).json()["items"]]
    assert "Group visible item!!" in names


# ---------------------------------------------------------------------------
# Permission checks: patch / delete / read by ID now use owner, not creator
# ---------------------------------------------------------------------------

def test_patch_by_owner_after_transfer(auth_headers, session):
    """After ownership is transferred, the new owner can patch the item."""
    client, user = auth_headers
    friend = _make_friend(session, user, "newowner1")
    friend_client = _make_friend_client(session, friend)

    item_id = client.post("/items/", params={"name": "Transfer patch test!!"}).json()["id"]
    client.post(f"/items/{item_id}/assign/user/{friend.username}")

    response = friend_client.patch(f"/items/{item_id}", json={"name": "Patched by new ownr"})
    assert response.status_code == 200
    assert response.json()["name"] == "Patched by new ownr"


def test_patch_by_old_owner_after_transfer_returns_403(auth_headers, session):
    """After transferring ownership, the original creator can no longer patch."""
    client, user = auth_headers
    friend = _make_friend(session, user, "newowner2")

    item_id = client.post("/items/", params={"name": "Old owner patch test"}).json()["id"]
    client.post(f"/items/{item_id}/assign/user/{friend.username}")

    assert client.patch(f"/items/{item_id}", json={"name": "Steal patch attempt"}).status_code == 403


def test_delete_by_owner_after_transfer(auth_headers, session):
    """After ownership is transferred, the new owner can delete the item."""
    client, user = auth_headers
    friend = _make_friend(session, user, "newowner3")
    friend_client = _make_friend_client(session, friend)

    item_id = client.post("/items/", params={"name": "Transfer delete test!"}).json()["id"]
    client.post(f"/items/{item_id}/assign/user/{friend.username}")

    assert friend_client.delete(f"/items/{item_id}").json() == {"ok": True}


def test_read_item_by_group_member(auth_headers, session):
    """A group member (who is not the owner) can read an item by ID."""
    client, user = auth_headers
    friend = _make_friend(session, user, "groupmember1")
    group = db_groups.create(session, name="Read access grp", owner_id=user.id)
    db_groups.add_member(session, group.id, friend.id)
    friend_client = _make_friend_client(session, friend)

    item_id = client.post("/items/", params={"name": "Group read test item!"}).json()["id"]
    client.post(f"/items/{item_id}/assign/group/{group.id}")

    response = friend_client.get(f"/items/{item_id}")
    assert response.status_code == 200
    assert response.json()["id"] == item_id


def test_patch_by_group_member_is_forbidden(auth_headers, session):
    """A group member who is not the owner cannot patch the item."""
    client, user = auth_headers
    friend = _make_friend(session, user, "groupmember2")
    group = db_groups.create(session, name="No patch group", owner_id=user.id)
    db_groups.add_member(session, group.id, friend.id)
    friend_client = _make_friend_client(session, friend)

    item_id = client.post("/items/", params={"name": "Group no patch item!"}).json()["id"]
    client.post(f"/items/{item_id}/assign/group/{group.id}")

    assert friend_client.patch(f"/items/{item_id}", json={"name": "Unauthorized patch!"}).status_code == 403


def test_delete_by_group_member_is_forbidden(auth_headers, session):
    """A group member who is not the owner cannot delete the item."""
    client, user = auth_headers
    friend = _make_friend(session, user, "groupmember3")
    group = db_groups.create(session, name="No delete group", owner_id=user.id)
    db_groups.add_member(session, group.id, friend.id)
    friend_client = _make_friend_client(session, friend)

    item_id = client.post("/items/", params={"name": "Group no delete item"}).json()["id"]
    client.post(f"/items/{item_id}/assign/group/{group.id}")

    assert friend_client.delete(f"/items/{item_id}").status_code == 403


# ---------------------------------------------------------------------------
# Reorder by group member
# ---------------------------------------------------------------------------

def test_reorder_by_group_member(auth_headers, session):
    """A group member (non-owner) can reorder an item they can see."""
    client, user = auth_headers
    friend = _make_friend(session, user, "reordermember1")
    group = db_groups.create(session, name="Reorder group", owner_id=user.id)
    db_groups.add_member(session, group.id, friend.id)
    friend_client = _make_friend_client(session, friend)

    item_id = client.post("/items/", params={"name": "Reorder group item!!"}).json()["id"]
    client.post(f"/items/{item_id}/assign/group/{group.id}")

    response = friend_client.post(f"/items/{item_id}/reorder", json={"after_id": None})
    assert response.status_code == 200
    assert "order_key" in response.json()


def test_reorder_after_id_by_group_member(auth_headers, session):
    """A group member can use another visible item as the after_id anchor."""
    client, user = auth_headers
    friend = _make_friend(session, user, "reordermember2")
    group = db_groups.create(session, name="Reorder group 2", owner_id=user.id)
    db_groups.add_member(session, group.id, friend.id)
    friend_client = _make_friend_client(session, friend)

    item_a = client.post("/items/", params={"name": "Reorder anchor itemaa"}).json()["id"]
    item_b = client.post("/items/", params={"name": "Reorder target itembb"}).json()["id"]
    client.post(f"/items/{item_a}/assign/group/{group.id}")
    client.post(f"/items/{item_b}/assign/group/{group.id}")

    response = friend_client.post(f"/items/{item_b}/reorder", json={"after_id": item_a})
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Group unassignment
# ---------------------------------------------------------------------------

def test_unassign_group(auth_headers, session):
    """Owner can unset the group via DELETE /{id}/assign/group."""
    client, user = auth_headers
    friend = _make_friend(session, user, "ungroupmember1")
    group = db_groups.create(session, name="Unassign group", owner_id=user.id)
    db_groups.add_member(session, group.id, friend.id)
    friend_client = _make_friend_client(session, friend)

    item_id = client.post("/items/", params={"name": "Unassign group item!"}).json()["id"]
    client.post(f"/items/{item_id}/assign/group/{group.id}")

    # Group member can see it
    names = [i["name"] for i in friend_client.get("/items/", params={"size": 100}).json()["items"]]
    assert "Unassign group item!" in names

    # Owner unsets the group
    assert client.delete(f"/items/{item_id}/assign/group").json() == {"ok": True}

    # Group member can no longer see it
    names = [i["name"] for i in friend_client.get("/items/", params={"size": 100}).json()["items"]]
    assert "Unassign group item!" not in names


def test_unassign_group_non_owner_returns_403(auth_headers, session):
    """A non-owner cannot unset the group."""
    client, user = auth_headers
    friend = _make_friend(session, user, "ungroupmember2")
    group = db_groups.create(session, name="No unassign group", owner_id=user.id)
    db_groups.add_member(session, group.id, friend.id)
    friend_client = _make_friend_client(session, friend)

    item_id = client.post("/items/", params={"name": "Non owner unassign!!"}).json()["id"]
    client.post(f"/items/{item_id}/assign/group/{group.id}")

    assert friend_client.delete(f"/items/{item_id}/assign/group").status_code == 403


# ---------------------------------------------------------------------------
# Ownership transfer with group constraint
# ---------------------------------------------------------------------------

def test_transfer_ownership_new_owner_not_in_group_returns_403(auth_headers, session):
    """If the item is in a group and the new owner is not in that group, transfer is denied."""
    client, user = auth_headers
    friend = _make_friend(session, user, "transferfriend1")
    group = db_groups.create(session, name="Constrained group", owner_id=user.id)
    # friend is NOT added to the group

    item_id = client.post("/items/", params={"name": "Group constrained item"}).json()["id"]
    client.post(f"/items/{item_id}/assign/group/{group.id}")

    response = client.post(f"/items/{item_id}/assign/user/{friend.username}")
    assert response.status_code == 403


def test_transfer_ownership_new_owner_in_group(auth_headers, session):
    """If the item is in a group and the new owner is also in that group, transfer succeeds."""
    client, user = auth_headers
    friend = _make_friend(session, user, "transferfriend2")
    group = db_groups.create(session, name="Shared owner group", owner_id=user.id)
    db_groups.add_member(session, group.id, friend.id)

    item_id = client.post("/items/", params={"name": "Group transfer item!!"}).json()["id"]
    client.post(f"/items/{item_id}/assign/group/{group.id}")

    response = client.post(f"/items/{item_id}/assign/user/{friend.username}")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# POST /items/search — filter by group_ids
# ---------------------------------------------------------------------------

def test_search_filter_by_group_ids(auth_headers, session):
    """group_ids filter returns only items assigned to those groups."""
    client, user = auth_headers
    group = db_groups.create(session, name="Filter group", owner_id=user.id)

    in_group  = client.post("/items/", params={"name": "Item in the group!!"}).json()["id"]
    not_group = client.post("/items/", params={"name": "Item not in group!!"}).json()["id"]
    client.post(f"/items/{in_group}/assign/group/{group.id}")

    result = _search(client, group_ids=[group.id])
    assert result.status_code == 200
    ids = [i["id"] for i in result.json()["items"]]
    assert in_group in ids
    assert not_group not in ids


def test_search_filter_group_ids_excludes_other_groups(auth_headers, session):
    """group_ids filter does not return items from groups not in the filter list."""
    client, user = auth_headers
    group_a = db_groups.create(session, name="Group A filter", owner_id=user.id)
    group_b = db_groups.create(session, name="Group B filter", owner_id=user.id)

    item_a = client.post("/items/", params={"name": "Item in group A aa!"}).json()["id"]
    item_b = client.post("/items/", params={"name": "Item in group B bb!"}).json()["id"]
    client.post(f"/items/{item_a}/assign/group/{group_a.id}")
    client.post(f"/items/{item_b}/assign/group/{group_b.id}")

    ids = [i["id"] for i in _search(client, group_ids=[group_a.id]).json()["items"]]
    assert item_a in ids
    assert item_b not in ids


def test_creator_can_read_item_by_id_after_reassignment(auth_headers, session):
    """Creator can still fetch an item by ID after ownership has been transferred."""
    client, user = auth_headers
    friend = _make_friend(session, user, "creator_friend1")

    item_id = client.post("/items/", params={"name": "Creator read by id"}).json()["id"]
    client.post(f"/items/{item_id}/assign/user/{friend.username}")

    response = client.get(f"/items/{item_id}")
    assert response.status_code == 200
    assert response.json()["id"] == item_id


def test_creator_item_appears_in_search_after_reassignment(auth_headers, session):
    """Creator's items are returned by /search even after ownership was transferred."""
    client, user = auth_headers
    friend = _make_friend(session, user, "creator_friend2")

    item_id = client.post("/items/", params={"name": "Creator search visibility"}).json()["id"]
    client.post(f"/items/{item_id}/assign/user/{friend.username}")

    ids = [i["id"] for i in _search(client).json()["items"]]
    assert item_id in ids
