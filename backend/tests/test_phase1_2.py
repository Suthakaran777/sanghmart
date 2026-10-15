import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select

from app.core.database import Base
from app.main import app
from app.core.security import get_password_hash
from app.repositories.base import Repository
from tests.conftest import test_engine, TestingSessionLocal

@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    async with TestingSessionLocal() as session:
        repo = Repository(session)
        admin = await repo.create_user("Admin User", "admin", get_password_hash("admin123"), role="admin")
        seller = await repo.create_user("Seller One", "seller1", get_password_hash("seller123"), role="seller")
        seller2 = await repo.create_user("Seller Two", "seller2", get_password_hash("seller123"), role="seller")
        
        nagar = await repo.create_nagar("Shivaji Nagar")
        item = await repo.create_item("Shirt", 300, ["38"])
        await session.commit()
        
        item_size = await repo.get_item_size(item.id, "38")
        await repo.update_stock(item_size.id, 1, "opening", "Initial stock 1", user_id=admin.id)
        await session.commit()
        
    yield
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_auth_and_login():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/auth/login", json={"username": "seller1", "password": "seller123"})
        assert res.status_code == 200
        data = res.json()
        assert data["role"] == "seller"
        assert "access_token" in data

@pytest.mark.asyncio
async def test_price_tampering_is_ignored():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        login_res = await ac.post("/auth/login", json={"username": "seller1", "password": "seller123"})
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        cat_res = await ac.get("/catalogue", headers=headers)
        items = cat_res.json()["items"]
        item = items[0]
        nagar = cat_res.json()["nagars"][0]

        order_payload = {
            "buyer_name": "Ravi Kumar",
            "buyer_phone": "9876543210",
            "nagar_id": nagar["id"],
            "items": [{"item_id": item["id"], "size": "38", "quantity": 1}],
            "pay_now": True,
            "payment_method": "cash"
        }

        res = await ac.post("/orders", json=order_payload, headers=headers)
        assert res.status_code == 200
        order_data = res.json()
        
        assert order_data["total"] == 300
        assert order_data["items"][0]["unit_price"] == 300
        assert order_data["payment_status"] == "Paid"
        assert order_data["bill_no"].startswith("SM-2026-")

@pytest.mark.asyncio
async def test_idempotency_key_prevents_duplicate_orders():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        login_res = await ac.post("/auth/login", json={"username": "seller1", "password": "seller123"})
        token = login_res.json()["access_token"]
        headers = {
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": "test-idem-key-12345"
        }

        cat_res = await ac.get("/catalogue", headers=headers)
        item = cat_res.json()["items"][0]
        nagar = cat_res.json()["nagars"][0]

        order_payload = {
            "buyer_name": "Anil",
            "buyer_phone": "9876500000",
            "nagar_id": nagar["id"],
            "items": [{"item_id": item["id"], "size": "38", "quantity": 1}],
            "pay_now": True,
            "payment_method": "cash"
        }

        res1 = await ac.post("/orders", json=order_payload, headers=headers)
        assert res1.status_code == 200
        order1 = res1.json()

        res2 = await ac.post("/orders", json=order_payload, headers=headers)
        assert res2.status_code == 200
        order2 = res2.json()

        assert order1["id"] == order2["id"]
        assert order1["bill_no"] == order2["bill_no"]

@pytest.mark.asyncio
async def test_oversell_protection():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        s1_login = await ac.post("/auth/login", json={"username": "seller1", "password": "seller123"})
        s1_token = s1_login.json()["access_token"]

        s2_login = await ac.post("/auth/login", json={"username": "seller2", "password": "seller123"})
        s2_token = s2_login.json()["access_token"]

        cat_res = await ac.get("/catalogue", headers={"Authorization": f"Bearer {s1_token}"})
        item = cat_res.json()["items"][0]
        nagar = cat_res.json()["nagars"][0]

        order_payload = {
            "buyer_name": "Buyer A",
            "buyer_phone": "9111111111",
            "nagar_id": nagar["id"],
            "items": [{"item_id": item["id"], "size": "38", "quantity": 1}],
            "pay_now": False
        }

        res1 = await ac.post("/orders", json=order_payload, headers={"Authorization": f"Bearer {s1_token}"})
        assert res1.status_code == 200

        res2 = await ac.post("/orders", json=order_payload, headers={"Authorization": f"Bearer {s2_token}"})
        assert res2.status_code == 409
