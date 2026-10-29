def register(client, username, invite):
    return client.post("/api/auth/register", json={"username": username, "display_name": username.title(), "password": "SicheresPasswort!23", "invite_code": invite})


def csrf(client):
    return {"X-CSRF-Token": client.cookies.get("dkl_csrf", "")}


def test_registration_login_and_unique_invite(client):
    first = register(client, "max", "ALPHA")
    assert first.status_code == 200
    assert len(first.json()["dkl_number"]) == 8
    client.post("/api/auth/logout", headers=csrf(client))
    assert register(client, "other", "ALPHA").status_code == 400
    assert client.post("/api/auth/login", json={"login": "max", "password": "SicheresPasswort!23"}).status_code == 200


def test_two_users_can_become_contacts_and_message(client):
    a = register(client, "anna", "ALPHA").json()
    cookies_a = dict(client.cookies)
    client.cookies.clear()
    b = register(client, "ben", "BETA").json()
    cookies_b = dict(client.cookies)
    client.cookies.clear(); client.cookies.update(cookies_a)
    response = client.post("/api/friends/requests", json={"dkl_number": b["dkl_number"]}, headers=csrf(client))
    assert response.status_code == 200
    client.cookies.clear(); client.cookies.update(cookies_b)
    pending = client.get("/api/friends/requests").json()
    assert len(pending) == 1
    assert client.post(f"/api/friends/requests/{pending[0]['request_id']}/accept", headers=csrf(client)).status_code == 200
    sent = client.post(f"/api/messages/{a['id']}", json={"body": "Hallo Anna!"}, headers=csrf(client))
    assert sent.status_code == 200
    assert client.get(f"/api/messages/{a['id']}").json()[0]["body"] == "Hallo Anna!"


def test_messages_are_not_public(client):
    a = register(client, "anna", "ALPHA").json()
    client.cookies.clear()
    register(client, "ben", "BETA")
    assert client.get(f"/api/messages/{a['id']}").status_code == 403

