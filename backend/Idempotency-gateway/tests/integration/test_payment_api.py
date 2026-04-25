from __future__ import annotations

import asyncio
import os

import pytest
import pytest_asyncio

os.environ.setdefault("PAYMENT_SIMULATED_DELAY_SECONDS", "0.2")
os.environ.setdefault("IDEMPOTENCY_TTL_SECONDS", "30")
os.environ.setdefault("LOG_LEVEL", "WARNING")  # keep test output quiet

from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.main import create_app  # noqa: E402


@pytest_asyncio.fixture
async def client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        async with app.router.lifespan_context(app):
            yield c


@pytest.mark.asyncio
async def test_first_request_succeeds_without_cache_header(client):
    r = await client.post(
        "/process-payment",
        headers={"Idempotency-Key": "k-first"},
        json={"amount": 100, "currency": "USD"},
    )
    assert r.status_code == 200
    assert r.headers.get("x-cache-hit") is None
    data = r.json()
    assert data["status"] == "succeeded"
    assert data["message"] == "Charged 100.0 USD"
    assert data["chargeId"].startswith("ch_")


@pytest.mark.asyncio
async def test_duplicate_same_body_returns_cache_hit(client):
    headers = {"Idempotency-Key": "k-dup"}
    body = {"amount": 50, "currency": "EUR"}
    r1 = await client.post("/process-payment", headers=headers, json=body)
    r2 = await client.post("/process-payment", headers=headers, json=body)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r2.headers.get("x-cache-hit") == "true"
    assert r1.json()["chargeId"] == r2.json()["chargeId"]


@pytest.mark.asyncio
async def test_same_key_different_body_returns_409(client):
    headers = {"Idempotency-Key": "k-conflict"}
    r1 = await client.post("/process-payment", headers=headers,
                           json={"amount": 10, "currency": "USD"})
    r2 = await client.post("/process-payment", headers=headers,
                           json={"amount": 11, "currency": "USD"})
    assert r1.status_code == 200
    assert r2.status_code == 409
    assert r2.json()["error"] == "idempotency_conflict"


@pytest.mark.asyncio
async def test_missing_idempotency_key_returns_400(client):
    r = await client.post(
        "/process-payment",
        json={"amount": 1, "currency": "USD"},
    )
    assert r.status_code == 400
    assert r.json()["error"] == "missing_idempotency_key"


@pytest.mark.asyncio
async def test_invalid_json_returns_400(client):
    r = await client.post(
        "/process-payment",
        headers={"Idempotency-Key": "k-badjson", "Content-Type": "application/json"},
        content=b"{not valid json",
    )
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_json"


@pytest.mark.asyncio
async def test_invalid_amount_returns_400(client):
    r = await client.post(
        "/process-payment",
        headers={"Idempotency-Key": "k-badamount"},
        json={"amount": -1, "currency": "USD"},
    )
    assert r.status_code == 400
    assert r.json()["error"] == "validation_error"


@pytest.mark.asyncio
async def test_concurrent_duplicates_run_handler_once(client):
    headers = {"Idempotency-Key": "k-concurrent"}
    body = {"amount": 7.5, "currency": "GBP"}

    results = await asyncio.gather(
        *(client.post("/process-payment", headers=headers, json=body) for _ in range(5))
    )

    assert all(r.status_code == 200 for r in results)
    charge_ids = {r.json()["chargeId"] for r in results}
    assert len(charge_ids) == 1
    fresh = [r for r in results if r.headers.get("x-cache-hit") != "true"]
    assert len(fresh) == 1


@pytest.mark.asyncio
async def test_key_order_insensitive_body_matching(client):
    # same body, different key order — should not trigger a conflict
    headers = {"Idempotency-Key": "k-order"}
    r1 = await client.post("/process-payment", headers=headers,
                           json={"amount": 2, "currency": "USD"})
    r2 = await client.post("/process-payment", headers=headers,
                           json={"currency": "USD", "amount": 2})
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r2.headers.get("x-cache-hit") == "true"


@pytest.mark.asyncio
async def test_health_endpoint(client):
    r = await client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "idempotencyEntries" in data
