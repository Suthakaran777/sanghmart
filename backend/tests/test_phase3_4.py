import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

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
        seller1 = await repo.create_user("Seller One", "seller1", get_password_hash("seller123"), role="seller")
        seller2 = await repo.create_user("Seller Two", "seller2", get_password_hash("seller123"), role="seller")
        
        nagar = await repo.create_nagar("Shivaji Nagar")
        item = await repo.create_item("Pant", 400, ["32"])
        await session.commit()
        
        item_size = await repo.get_item_size(item.id, "32")
        await repo.update_stock(item_size.id, 50, "opening", "Initial stock 50", user_id=admin.id)
        await session.commit()
        
    yield
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_pending_math_and_advance_collection():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        s1_login = await ac.post("/auth/login", json={"username": "seller1", "password": "seller123"})
        token = s1_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        cat = (await ac.get("/catalogue", headers=headers)).json()
        item_id = cat["items"][0]["id"]
        nagar_id = cat["nagars"][0]["id"]

        order_payload = {
            "buyer_name": "Suresh",
            "buyer_phone": "9876543210",
            "nagar_id": nagar_id,
            "items": [{"item_id": item_id, "size": "32", "quantity": 2}],
            "pay_now": False,
            "advance_amount": 300,
            "payment_method": "cash"
        }
        res = await ac.post("/orders", json=order_payload, headers=headers)
        assert res.status_code == 200
        order = res.json()
        assert order["total"] == 800
        assert order["paid_amount"] == 300
        assert order["balance"] == 500
        assert order["payment_status"] == "Partial"

        # Overpayment test
        overpay_res = await ac.post("/payments/collect", json={
            "order_id": order["id"],
            "amount": 600,
            "method": "cash"
        }, headers=headers)
        assert overpay_res.status_code == 400
        assert "exceeds remaining balance" in overpay_res.json()["detail"]

        # Pay exact balance: 500
        pay_res = await ac.post("/payments/collect", json={
            "order_id": order["id"],
            "amount": 500,
            "method": "upi",
            "utr": "123456789012"
        }, headers=headers)
        assert pay_res.status_code == 200

        updated_order = (await ac.get(f"/orders/{order['id']}", headers=headers)).json()
        assert updated_order["paid_amount"] == 800
        assert updated_order["balance"] == 0
        assert updated_order["payment_status"] == "Paid"

@pytest.mark.asyncio
async def test_seller_isolation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        s1_token = (await ac.post("/auth/login", json={"username": "seller1", "password": "seller123"})).json()["access_token"]
        s2_token = (await ac.post("/auth/login", json={"username": "seller2", "password": "seller123"})).json()["access_token"]

        cat = (await ac.get("/catalogue", headers={"Authorization": f"Bearer {s1_token}"})).json()
        item_id = cat["items"][0]["id"]
        nagar_id = cat["nagars"][0]["id"]

        order = (await ac.post("/orders", json={
            "buyer_name": "Private Buyer",
            "buyer_phone": "9988776655",
            "nagar_id": nagar_id,
            "items": [{"item_id": item_id, "size": "32", "quantity": 1}],
            "pay_now": False
        }, headers={"Authorization": f"Bearer {s1_token}"})).json()

        view_res = await ac.get(f"/orders/{order['id']}", headers={"Authorization": f"Bearer {s2_token}"})
        assert view_res.status_code == 403

        collect_res = await ac.post("/payments/collect", json={
            "order_id": order["id"],
            "amount": 400,
            "method": "cash"
        }, headers={"Authorization": f"Bearer {s2_token}"})
        assert collect_res.status_code == 403

@pytest.mark.asyncio
async def test_duplicate_utr_is_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        s1_token = (await ac.post("/auth/login", json={"username": "seller1", "password": "seller123"})).json()["access_token"]
        headers = {"Authorization": f"Bearer {s1_token}"}

        cat = (await ac.get("/catalogue", headers=headers)).json()
        item_id = cat["items"][0]["id"]
        nagar_id = cat["nagars"][0]["id"]

        order1 = (await ac.post("/orders", json={
            "buyer_name": "Buyer 1",
            "buyer_phone": "9999911111",
            "nagar_id": nagar_id,
            "items": [{"item_id": item_id, "size": "32", "quantity": 1}],
            "pay_now": False
        }, headers=headers)).json()

        order2 = (await ac.post("/orders", json={
            "buyer_name": "Buyer 2",
            "buyer_phone": "9999922222",
            "nagar_id": nagar_id,
            "items": [{"item_id": item_id, "size": "32", "quantity": 1}],
            "pay_now": False
        }, headers=headers)).json()

        p1 = await ac.post("/payments/collect", json={
            "order_id": order1["id"],
            "amount": 200,
            "method": "upi",
            "utr": "DUPLICATE_UTR_999"
        }, headers=headers)
        assert p1.status_code == 200

        p2 = await ac.post("/payments/collect", json={
            "order_id": order2["id"],
            "amount": 200,
            "method": "upi",
            "utr": "DUPLICATE_UTR_999"
        }, headers=headers)
        assert p2.status_code == 400
        assert "already been recorded" in p2.json()["detail"]

@pytest.mark.asyncio
async def test_pdf_bill_generation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        s1_token = (await ac.post("/auth/login", json={"username": "seller1", "password": "seller123"})).json()["access_token"]
        headers = {"Authorization": f"Bearer {s1_token}"}

        cat = (await ac.get("/catalogue", headers=headers)).json()
        order = (await ac.post("/orders", json={
            "buyer_name": "PDF Buyer",
            "buyer_phone": "9876543210",
            "nagar_id": cat["nagars"][0]["id"],
            "items": [{"item_id": cat["items"][0]["id"], "size": "32", "quantity": 1}],
            "pay_now": True,
            "payment_method": "cash"
        }, headers=headers)).json()

        pdf_res = await ac.get(f"/payments/pdf/{order['id']}", headers=headers)
        assert pdf_res.status_code == 200
        assert pdf_res.headers["content-type"] == "application/pdf"
        assert pdf_res.content.startswith(b"%PDF")
