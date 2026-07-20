from app.data.models import CallLog, Customer

TEST_PHONE = "+201091894094"


def test_create_customer(client, db_session) -> None:
    response = client.post("/api/customers", json={"name": "Mona Ali", "phone": TEST_PHONE, "notes": "VIP"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Mona Ali"
    assert body["phone"] == TEST_PHONE
    assert body["notes"] == "VIP"

    row = db_session.get(Customer, body["id"])
    assert row.phone == TEST_PHONE


def test_create_customer_without_notes(client) -> None:
    response = client.post("/api/customers", json={"name": "Ahmed", "phone": "+201000000001"})
    assert response.status_code == 201
    assert response.json()["notes"] is None


def test_create_customer_duplicate_phone_is_409(client) -> None:
    client.post("/api/customers", json={"name": "Mona Ali", "phone": TEST_PHONE})
    response = client.post("/api/customers", json={"name": "Someone Else", "phone": TEST_PHONE})
    assert response.status_code == 409


def test_list_customers_newest_first(client) -> None:
    client.post("/api/customers", json={"name": "First", "phone": "+201000000002"})
    client.post("/api/customers", json={"name": "Second", "phone": "+201000000003"})

    response = client.get("/api/customers")
    assert response.status_code == 200
    names = [c["name"] for c in response.json()]
    assert names == ["Second", "First"]


def test_get_customer_includes_empty_call_history(client) -> None:
    created = client.post("/api/customers", json={"name": "Mona Ali", "phone": TEST_PHONE}).json()

    response = client.get(f"/api/customers/{created['id']}")
    assert response.status_code == 200
    assert response.json()["call_history"] == []


def test_get_customer_missing_is_404(client) -> None:
    response = client.get("/api/customers/999999")
    assert response.status_code == 404


def test_delete_customer(client, db_session) -> None:
    created = client.post("/api/customers", json={"name": "Mona Ali", "phone": TEST_PHONE}).json()

    response = client.delete(f"/api/customers/{created['id']}")
    assert response.status_code == 204
    assert db_session.get(Customer, created["id"]) is None


def test_delete_customer_missing_is_404(client) -> None:
    response = client.delete("/api/customers/999999")
    assert response.status_code == 404


def test_delete_customer_keeps_call_history_with_null_customer_id(client, db_session) -> None:
    customer = client.post("/api/customers", json={"name": "Mona Ali", "phone": TEST_PHONE}).json()
    flagged = client.post(f"/api/customers/{customer['id']}/flag", json={"ticket_id": "TCK-1"}).json()

    client.delete(f"/api/customers/{customer['id']}")

    call = db_session.get(CallLog, flagged["id"])
    assert call is not None
    assert call.customer_id is None


def test_flag_for_follow_up_creates_queued_call(client, db_session) -> None:
    customer = client.post("/api/customers", json={"name": "Mona Ali", "phone": TEST_PHONE}).json()

    response = client.post(f"/api/customers/{customer['id']}/flag", json={"ticket_id": "TCK-1"})
    assert response.status_code == 201
    body = response.json()
    assert body["customer_id"] == customer["id"]
    assert body["customer_phone"] == TEST_PHONE
    assert body["status"] == "queued"

    row = db_session.get(CallLog, body["id"])
    assert row.customer_id == customer["id"]
    assert row.ticket_id == "TCK-1"
    assert row.status == "queued"


def test_flag_for_follow_up_without_ticket_id(client) -> None:
    customer = client.post("/api/customers", json={"name": "Mona Ali", "phone": TEST_PHONE}).json()

    response = client.post(f"/api/customers/{customer['id']}/flag", json={})
    assert response.status_code == 201
    assert response.json()["ticket_id"] is None


def test_flag_for_follow_up_missing_customer_is_404(client) -> None:
    response = client.post("/api/customers/999999/flag", json={})
    assert response.status_code == 404


def test_flagged_call_appears_in_call_history(client) -> None:
    customer = client.post("/api/customers", json={"name": "Mona Ali", "phone": TEST_PHONE}).json()
    client.post(f"/api/customers/{customer['id']}/flag", json={"ticket_id": "TCK-1"})

    response = client.get(f"/api/customers/{customer['id']}")
    history = response.json()["call_history"]
    assert len(history) == 1
    assert history[0]["ticket_id"] == "TCK-1"
    assert history[0]["status"] == "queued"
