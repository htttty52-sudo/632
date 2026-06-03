import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient):
    resp = await client.post("/api/auth/register", json={
        "username": "newuser", "password": "test123", "role": "user"
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert data["role"] == "user"

    resp = await client.post("/api/auth/login", json={
        "username": "newuser", "password": "test123"
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient):
    resp = await client.post("/api/auth/login", json={
        "username": "nobody", "password": "wrong"
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_duplicate_registration(client: AsyncClient):
    await client.post("/api/auth/register", json={
        "username": "dup", "password": "pass", "role": "user"
    })
    resp = await client.post("/api/auth/register", json={
        "username": "dup", "password": "pass2", "role": "user"
    })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_admin_endpoint_forbidden_for_user(client: AsyncClient, user_token: str):
    resp = await client.get(
        "/api/exchange-configs/",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_endpoint_allowed_for_admin(client: AsyncClient, admin_token: str):
    resp = await client.get(
        "/api/exchange-configs/",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_exchange_config_crud(client: AsyncClient, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}

    resp = await client.post("/api/exchange-configs/", json={
        "exchange_name": "binance", "api_key": "key123", "api_secret": "secret", "is_active": True
    }, headers=headers)
    assert resp.status_code == 201
    config_id = resp.json()["id"]

    resp = await client.get("/api/exchange-configs/", headers=headers)
    assert len(resp.json()) == 1

    resp = await client.put(f"/api/exchange-configs/{config_id}", json={
        "exchange_name": "binance", "api_key": "newkey", "api_secret": "newsecret", "is_active": False
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["api_key"] == "newkey"

    resp = await client.delete(f"/api/exchange-configs/{config_id}", headers=headers)
    assert resp.status_code == 204
