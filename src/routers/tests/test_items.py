from sqlmodel import Session

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
