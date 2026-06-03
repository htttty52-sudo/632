import os

os.environ["ARB_USE_MOCK"] = "true"
os.environ["ARB_DATABASE_URL"] = "sqlite+aiosqlite:///./test_arbitrage.db"
os.environ["ARB_JWT_SECRET"] = "test-secret"

import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.db.database import engine, Base
from app.main import app


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def user_token(client: AsyncClient):
    resp = await client.post("/api/auth/register", json={
        "username": "testuser", "password": "pass123", "role": "user"
    })
    assert resp.status_code == 201, f"Register failed: {resp.text}"
    resp = await client.post("/api/auth/login", json={
        "username": "testuser", "password": "pass123"
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def admin_token(client: AsyncClient):
    resp = await client.post("/api/auth/register", json={
        "username": "admin", "password": "admin123", "role": "admin"
    })
    assert resp.status_code == 201, f"Register failed: {resp.text}"
    resp = await client.post("/api/auth/login", json={
        "username": "admin", "password": "admin123"
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]
