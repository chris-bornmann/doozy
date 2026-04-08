from sqlmodel import Session, select

from db.models import Item, ItemTag, Tag
from db.users import create_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_tag(client, name: str) -> int:
    return client.post("/tags/", json={"name": name}).json()["id"]


# ---------------------------------------------------------------------------
# POST /tags/
# ---------------------------------------------------------------------------

def test_create_tag_returns_tag(auth_headers):
    client, _ = auth_headers
    response = client.post("/tags/", json={"name": "backend"})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "backend"
    assert "id" in data


def test_create_tag_too_long(auth_headers):
    client, _ = auth_headers
    assert client.post("/tags/", json={"name": "a" * 17}).status_code == 422


def test_create_tag_empty_name(auth_headers):
    client, _ = auth_headers
    assert client.post("/tags/", json={"name": ""}).status_code == 422


def test_create_tag_duplicate(auth_headers):
    client, _ = auth_headers
    client.post("/tags/", json={"name": "unique"})
    assert client.post("/tags/", json={"name": "unique"}).status_code == 409


def test_create_tag_requires_auth(client):
    assert client.post("/tags/", json={"name": "nope"}).status_code == 401


# ---------------------------------------------------------------------------
# GET /tags/
# ---------------------------------------------------------------------------

def test_list_tags_empty(auth_headers):
    client, _ = auth_headers
    response = client.get("/tags/")
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_list_tags_alphabetical(auth_headers):
    client, _ = auth_headers
    for name in ["zebra", "apple", "mango"]:
        client.post("/tags/", json={"name": name})
    names = [t["name"] for t in client.get("/tags/", params={"size": 100}).json()["items"]]
    assert names == sorted(names)


def test_list_tags_default_page_size(auth_headers):
    client, _ = auth_headers
    for i in range(15):
        client.post("/tags/", json={"name": f"tag{i:02d}"})
    data = client.get("/tags/").json()
    assert data["size"] == 10
    assert len(data["items"]) == 10


def test_list_tags_custom_size(auth_headers):
    client, _ = auth_headers
    for i in range(5):
        client.post("/tags/", json={"name": f"t{i}"})
    data = client.get("/tags/", params={"size": 3}).json()
    assert len(data["items"]) == 3


def test_list_tags_match(auth_headers):
    client, _ = auth_headers
    client.post("/tags/", json={"name": "frontend"})
    client.post("/tags/", json={"name": "backend"})
    client.post("/tags/", json={"name": "end-to-end"})
    names = [t["name"] for t in client.get("/tags/", params={"match": "end", "size": 100}).json()["items"]]
    assert set(names) == {"frontend", "backend", "end-to-end"}


def test_list_tags_match_no_results(auth_headers):
    client, _ = auth_headers
    client.post("/tags/", json={"name": "python"})
    data = client.get("/tags/", params={"match": "java"}).json()
    assert data["items"] == []


def test_list_tags_requires_auth(client):
    assert client.get("/tags/").status_code == 401


# ---------------------------------------------------------------------------
# DELETE /tags/{id}
# ---------------------------------------------------------------------------

def test_delete_tag(auth_headers):
    client, _ = auth_headers
    tag_id = _create_tag(client, "removeme")
    assert client.delete(f"/tags/{tag_id}").status_code == 200
    names = [t["name"] for t in client.get("/tags/", params={"size": 100}).json()["items"]]
    assert "removeme" not in names


def test_delete_tag_not_found(auth_headers):
    client, _ = auth_headers
    assert client.delete("/tags/9999").status_code == 404


def test_delete_tag_removes_item_tag_entries(auth_headers, session):
    client, user = auth_headers
    item = Item(name="Tagged item aaaaa", creator_id=user.id)
    session.add(item)
    session.commit()
    session.refresh(item)

    tag_id = _create_tag(client, "todelete")
    session.add(ItemTag(item_id=item.id, tag_id=tag_id))
    session.commit()

    client.delete(f"/tags/{tag_id}")
    remaining = session.exec(select(ItemTag).where(ItemTag.tag_id == tag_id)).all()
    assert remaining == []


def test_delete_tag_requires_auth(client):
    assert client.delete("/tags/1").status_code == 401
