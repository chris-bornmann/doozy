from sqlmodel import select

from db.models import Item, ItemOwnership, ItemTag, Tag
from db.users import create_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_item(session, user, name="Test item aaaa"):
    item = Item(name=name, creator_id=user.id)
    session.add(item)
    session.flush()
    session.add(ItemOwnership(item_id=item.id, user_id=user.id))
    session.commit()
    session.refresh(item)
    return item


def _make_tag(session, name="testtag"):
    tag = Tag(name=name)
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return tag


# ---------------------------------------------------------------------------
# POST /item_tags/
# ---------------------------------------------------------------------------

def test_assign_tag(auth_headers, session):
    client, user = auth_headers
    item = _make_item(session, user)
    tag  = _make_tag(session)
    response = client.post("/item_tags/", json={"item_id": item.id, "tag_id": tag.id})
    assert response.status_code == 200
    data = response.json()
    assert data["item_id"] == item.id
    assert data["tag_id"]  == tag.id


def test_assign_tag_duplicate(auth_headers, session):
    client, user = auth_headers
    item = _make_item(session, user)
    tag  = _make_tag(session)
    client.post("/item_tags/", json={"item_id": item.id, "tag_id": tag.id})
    assert client.post("/item_tags/", json={"item_id": item.id, "tag_id": tag.id}).status_code == 409


def test_assign_tag_item_not_found(auth_headers, session):
    client, _ = auth_headers
    tag = _make_tag(session)
    assert client.post("/item_tags/", json={"item_id": 9999, "tag_id": tag.id}).status_code == 404


def test_assign_tag_tag_not_found(auth_headers, session):
    client, user = auth_headers
    item = _make_item(session, user)
    assert client.post("/item_tags/", json={"item_id": item.id, "tag_id": 9999}).status_code == 404


def test_assign_tag_wrong_owner(auth_headers, session):
    client, _ = auth_headers
    other = create_user(session, username="otheruserA1", password="password1234")
    item  = _make_item(session, other, name="Other user item!")
    tag   = _make_tag(session)
    assert client.post("/item_tags/", json={"item_id": item.id, "tag_id": tag.id}).status_code == 403


def test_assign_tag_requires_auth(client):
    assert client.post("/item_tags/", json={"item_id": 1, "tag_id": 1}).status_code == 401


# ---------------------------------------------------------------------------
# GET /item_tags/?by=item&id=…
# ---------------------------------------------------------------------------

def test_list_tags_for_item(auth_headers, session):
    client, user = auth_headers
    item  = _make_item(session, user)
    tag1  = _make_tag(session, "alpha")
    tag2  = _make_tag(session, "beta")
    session.add_all([ItemTag(item_id=item.id, tag_id=tag1.id),
                     ItemTag(item_id=item.id, tag_id=tag2.id)])
    session.commit()
    response = client.get("/item_tags/", params={"by": "item", "id": item.id})
    assert response.status_code == 200
    names = {t["name"] for t in response.json()["items"]}
    assert names == {"alpha", "beta"}


def test_list_tags_for_item_empty(auth_headers, session):
    client, user = auth_headers
    item = _make_item(session, user)
    response = client.get("/item_tags/", params={"by": "item", "id": item.id})
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_list_tags_for_item_not_found(auth_headers):
    client, _ = auth_headers
    assert client.get("/item_tags/", params={"by": "item", "id": 9999}).status_code == 404


def test_list_tags_for_item_wrong_owner(auth_headers, session):
    client, _ = auth_headers
    other = create_user(session, username="otheruserB2", password="password1234")
    item  = _make_item(session, other, name="Belongs to other!")
    assert client.get("/item_tags/", params={"by": "item", "id": item.id}).status_code == 403


# ---------------------------------------------------------------------------
# GET /item_tags/?by=tag&id=…
# ---------------------------------------------------------------------------

def test_list_items_for_tag(auth_headers, session):
    client, user = auth_headers
    item1 = _make_item(session, user, "First item aaaaa")
    item2 = _make_item(session, user, "Second item bbbb")
    tag   = _make_tag(session, "shared")
    session.add_all([ItemTag(item_id=item1.id, tag_id=tag.id),
                     ItemTag(item_id=item2.id, tag_id=tag.id)])
    session.commit()
    response = client.get("/item_tags/", params={"by": "tag", "id": tag.id})
    assert response.status_code == 200
    ids = {i["id"] for i in response.json()["items"]}
    assert ids == {item1.id, item2.id}


def test_list_items_for_tag_only_current_user(auth_headers, session):
    client, user = auth_headers
    other      = create_user(session, username="otheruserC3", password="password1234")
    my_item    = _make_item(session, user,  "My item aaaaaa")
    their_item = _make_item(session, other, "Their item aaaa")
    tag        = _make_tag(session, "shared2")
    session.add_all([ItemTag(item_id=my_item.id,    tag_id=tag.id),
                     ItemTag(item_id=their_item.id, tag_id=tag.id)])
    session.commit()
    response = client.get("/item_tags/", params={"by": "tag", "id": tag.id})
    ids = {i["id"] for i in response.json()["items"]}
    assert ids == {my_item.id}


def test_list_items_for_tag_not_found(auth_headers):
    client, _ = auth_headers
    assert client.get("/item_tags/", params={"by": "tag", "id": 9999}).status_code == 404


def test_list_item_tags_requires_auth(client):
    assert client.get("/item_tags/", params={"by": "item", "id": 1}).status_code == 401


# ---------------------------------------------------------------------------
# DELETE /item_tags/
# ---------------------------------------------------------------------------

def test_remove_assignment(auth_headers, session):
    client, user = auth_headers
    item = _make_item(session, user)
    tag  = _make_tag(session)
    session.add(ItemTag(item_id=item.id, tag_id=tag.id))
    session.commit()
    response = client.request("DELETE", "/item_tags/", json={"item_id": item.id, "tag_id": tag.id})
    assert response.status_code == 200
    remaining = session.exec(select(ItemTag).where(ItemTag.item_id == item.id)).all()
    assert remaining == []


def test_remove_assignment_not_found(auth_headers, session):
    client, user = auth_headers
    item = _make_item(session, user)
    tag  = _make_tag(session)
    assert client.request("DELETE", "/item_tags/", json={"item_id": item.id, "tag_id": tag.id}).status_code == 404


def test_remove_assignment_wrong_owner(auth_headers, session):
    client, _ = auth_headers
    other = create_user(session, username="otheruserD4", password="password1234")
    item  = _make_item(session, other, name="Not mine itemaa")
    tag   = _make_tag(session)
    session.add(ItemTag(item_id=item.id, tag_id=tag.id))
    session.commit()
    assert client.request("DELETE", "/item_tags/", json={"item_id": item.id, "tag_id": tag.id}).status_code == 403


def test_remove_assignment_requires_auth(client):
    assert client.request("DELETE", "/item_tags/", json={"item_id": 1, "tag_id": 1}).status_code == 401
