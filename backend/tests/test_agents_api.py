from app.data.models import Agent

TEST_EMAIL = "mona.ali@callcenter.example"


def test_create_agent(client, db_session) -> None:
    response = client.post("/api/agents", json={"name": "Mona Ali", "email": TEST_EMAIL})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Mona Ali"
    assert body["email"] == TEST_EMAIL

    row = db_session.get(Agent, body["id"])
    assert row.email == TEST_EMAIL


def test_create_agent_duplicate_email_is_409(client) -> None:
    client.post("/api/agents", json={"name": "Mona Ali", "email": TEST_EMAIL})
    response = client.post("/api/agents", json={"name": "Someone Else", "email": TEST_EMAIL})
    assert response.status_code == 409


def test_list_agents_newest_first(client) -> None:
    client.post("/api/agents", json={"name": "First", "email": "first@callcenter.example"})
    client.post("/api/agents", json={"name": "Second", "email": "second@callcenter.example"})

    response = client.get("/api/agents")
    assert response.status_code == 200
    names = [a["name"] for a in response.json()]
    assert names == ["Second", "First"]


def test_delete_agent(client, db_session) -> None:
    created = client.post("/api/agents", json={"name": "Mona Ali", "email": TEST_EMAIL}).json()

    response = client.delete(f"/api/agents/{created['id']}")
    assert response.status_code == 204
    assert db_session.get(Agent, created["id"]) is None


def test_delete_agent_missing_is_404(client) -> None:
    response = client.delete("/api/agents/999999")
    assert response.status_code == 404
