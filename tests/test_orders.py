from order_api.models import Product

from .conftest import headers


def create(client, key="order-1", subject="customer-a", items=None):
    return client.post(
        "/api/v1/orders",
        headers=headers(subject=subject, key=key),
        json={"items": items or [{"product_id": 501, "quantity": 2}, {"product_id": 502, "quantity": 1}]},
    )


def test_create_retry_and_stock(client):
    api, factory = client
    first = create(api)
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["total_amount"] == "125.50"
    assert body["status"] == "pending"
    assert create(api).json() == body
    changed = create(api, items=[{"product_id": 501, "quantity": 1}])
    assert changed.status_code == 409
    with factory() as db:
        assert db.get(Product, 501).stock == 3
        assert db.get(Product, 502).stock == 2


def test_ownership_and_history(client):
    api, _ = client
    created = create(api).json()
    order_id = created["order_id"]
    customer_id = created["customer_id"]
    assert api.get("/api/v1/me", headers=headers()).json() == {"customer_id": customer_id}
    assert api.get(f"/api/v1/orders/{order_id}", headers=headers(subject="customer-b")).status_code == 404
    assert api.get(f"/api/v1/customers/{customer_id}/orders", headers=headers(subject="customer-b")).status_code == 404
    page = api.get("/api/v1/orders?status=pending&limit=1&offset=0", headers=headers()).json()
    assert page["total"] == 1
    assert page["items"][0]["order_id"] == order_id
    assert api.get(f"/api/v1/customers/{customer_id}/orders", headers=headers()).json()["total"] == 1


def test_staff_status_and_cancellation(client):
    api, factory = client
    order_id = create(api).json()["order_id"]
    url = f"/api/v1/orders/{order_id}/status"
    assert api.patch(url, headers=headers(), json={"status": "confirmed"}).status_code == 403
    assert api.patch(url, headers=headers(role="staff"), json={"status": "shipped"}).status_code == 409
    assert api.patch(url, headers=headers(role="staff"), json={"status": "confirmed"}).json()["status"] == "confirmed"
    cancelled = api.post(f"/api/v1/orders/{order_id}/cancel", headers=headers(), json={"reason": "Changed my mind"})
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert api.patch(url, headers=headers(role="staff"), json={"status": "shipped"}).status_code == 409
    with factory() as db:
        assert db.get(Product, 501).stock == 5


def test_shipped_order_cannot_be_cancelled(client):
    api, _ = client
    order_id = create(api).json()["order_id"]
    url = f"/api/v1/orders/{order_id}/status"
    for status in ("confirmed", "shipped"):
        assert api.patch(url, headers=headers(role="staff"), json={"status": status}).status_code == 200
    assert api.post(f"/api/v1/orders/{order_id}/cancel", headers=headers(), json={"reason": "Too late"}).status_code == 409


def test_invalid_stock_rolls_back_everything(client):
    api, factory = client
    result = create(api, items=[{"product_id": 501, "quantity": 2}, {"product_id": 502, "quantity": 4}])
    assert result.status_code == 409
    with factory() as db:
        assert db.get(Product, 501).stock == 5
        assert db.get(Product, 502).stock == 3
    assert create(api, items=[{"product_id": 501, "quantity": 1}]).status_code == 201


def test_gateway_and_validation(client):
    api, _ = client
    assert api.get("/api/v1/orders").status_code == 403
    assert api.get("/api/v1/orders", headers={**headers(), "x-gateway-secret": "wrong"}).status_code == 403
    assert api.get("/api/v1/orders", headers=headers(role="staff")).status_code == 403
    assert create(api, key=None).status_code == 400
    assert create(api, items=[{"product_id": 501, "quantity": 1}, {"product_id": 501, "quantity": 1}]).status_code == 422
    assert api.get("/health").json() == {"status": "ok"}

