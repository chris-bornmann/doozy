from sqlmodel import Session

from db.users import create_user


# ---------------------------------------------------------------------------
# GET /users/
# ---------------------------------------------------------------------------

def test_read_users_returns_list(auth_headers):
    client, _ = auth_headers
    response = client.get("/users/")
    assert response.status_code == 200
    assert "items" in response.json()


def test_read_users_requires_auth(client):
    assert client.get("/users/").status_code == 401


# ---------------------------------------------------------------------------
# GET /users/me
# ---------------------------------------------------------------------------

def test_read_user_me_returns_current_user(auth_headers):
    client, user = auth_headers
    response = client.get("/users/me")
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == user.username
    assert data["id"] == user.id


def test_read_user_me_omits_password(auth_headers):
    client, _ = auth_headers
    response = client.get("/users/me")
    assert "password" not in response.json()


def test_read_user_me_requires_auth(client):
    assert client.get("/users/me").status_code == 401


# ---------------------------------------------------------------------------
# GET /users/{id}
# ---------------------------------------------------------------------------

def test_read_user_by_id(auth_headers):
    client, user = auth_headers
    response = client.get(f"/users/{user.id}")
    assert response.status_code == 200
    assert response.json()["id"] == user.id


def test_read_user_by_id_not_found(auth_headers):
    client, _ = auth_headers
    assert client.get("/users/9999").status_code == 404


def test_read_user_by_id_omits_password(auth_headers):
    client, user = auth_headers
    response = client.get(f"/users/{user.id}")
    assert "password" not in response.json()


def test_read_user_by_id_requires_auth(client):
    assert client.get("/users/1").status_code == 401


# ---------------------------------------------------------------------------
# GET /users/{id}/items
# ---------------------------------------------------------------------------

def test_read_user_items_empty(auth_headers):
    client, user = auth_headers
    response = client.get(f"/users/{user.id}/items")
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_read_user_items_returns_only_that_users_items(auth_headers, session):
    client, user = auth_headers
    client.post("/items/", params={"name": "My task item"})

    other = create_user(session, username="otheruser1", password="password1234")
    from db.models import Item
    session.add(Item(name="Their task item", creator_id=other.id))
    session.commit()

    response = client.get(f"/users/{user.id}/items")
    assert response.status_code == 200
    names = [i["name"] for i in response.json()["items"]]
    assert "My task item" in names
    assert "Their task item" not in names


def test_read_user_items_requires_auth(client):
    assert client.get("/users/1/items").status_code == 401
