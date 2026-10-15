import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import Base
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
        
        nagar = await repo.create_nagar("Keshav Nagar")
        item = await repo.create_item("Belt", 150, ["Free Size"])
        await session.commit()
        
        item_size = await repo.get_item_size(item.id, "Free Size")
        await repo.update_stock(item_size.id, 20, "opening", "Initial 20", user_id=admin.id)
        await session.commit()
        
    yield
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_admin_metrics_and_isolation():
    """
    Test Phase 5:
    1. Verify admin can access /admin/dashboard-metrics.
    2. Verify regular seller is forbidden (403).
    3. Verify admin can cancel an order and stock returns.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin_login = await ac.post("/auth/login", json={"username": "admin", "password": "admin123"})
        admin_token = admin_login.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        seller_login = await ac.post("/auth/login", json={"username": "seller1", "password": "seller123"})
        seller_token = seller_login.json()["access_token"]
        seller_headers = {"Authorization": f"Bearer {seller_token}"}

        # 1. Seller forbidden from admin dashboard
        seller_deny = await ac.get("/admin/dashboard-metrics", headers=seller_headers)
        assert seller_deny.status_code == 403

        # 2. Admin allowed
        admin_metrics = await ac.get("/admin/dashboard-metrics", headers=admin_headers)
        assert admin_metrics.status_code == 200
        data = admin_metrics.json()
        assert "total_orders" in data
        assert "cash_total" in data
        assert "upi_total" in data

@pytest.mark.asyncio
async def test_order_cancellation_returns_stock():
    """
    Test Phase 5:
    Admin cancels order; stock is automatically returned to common pool.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin_token = (await ac.post("/auth/login", json={"username": "admin", "password": "admin123"})).json()["access_token"]
        seller_token = (await ac.post("/auth/login", json={"username": "seller1", "password": "seller123"})).json()["access_token"]

        cat = (await ac.get("/catalogue", headers={"Authorization": f"Bearer {seller_token}"})).json()
        item = cat["items"][0]
        nagar = cat["nagars"][0]
        initial_stock = item["sizes"][0]["stock_qty"]

        # Seller creates order for 2 items
        order = (await ac.post("/orders", json={
            "buyer_name": "Cancel Test",
            "buyer_phone": "9998887776",
            "nagar_id": nagar["id"],
            "items": [{"item_id": item["id"], "size": item["sizes"][0]["size"], "quantity": 2}],
            "pay_now": True,
            "payment_method": "cash"
        }, headers={"Authorization": f"Bearer {seller_token}"})).json()

        # Stock is now initial - 2
        cat2 = (await ac.get("/catalogue", headers={"Authorization": f"Bearer {seller_token}"})).json()
        assert cat2["items"][0]["sizes"][0]["stock_qty"] == initial_stock - 2

        # Admin cancels order with reason
        cancel_res = await ac.post(
            f"/admin/orders/{order['id']}/cancel",
            json={"reason": "Customer changed mind"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert cancel_res.status_code == 200

        # Stock is restored back to initial_stock
        cat3 = (await ac.get("/catalogue", headers={"Authorization": f"Bearer {seller_token}"})).json()
        assert cat3["items"][0]["sizes"][0]["stock_qty"] == initial_stock

        # Now test revert/restore order by admin
        revert_res = await ac.post(
            f"/admin/orders/{order['id']}/revert",
            json={"reason": "Customer called back to reinstate"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert revert_res.status_code == 200
        reverted_order = revert_res.json()
        assert reverted_order["order_status"] == "Active"
        assert reverted_order["cancel_reason"] is None

        # Stock is re-deducted back to initial_stock - 2
        cat4 = (await ac.get("/catalogue", headers={"Authorization": f"Bearer {seller_token}"})).json()
        assert cat4["items"][0]["sizes"][0]["stock_qty"] == initial_stock - 2

        # Seller can see order in /orders/mine as Active
        my_orders = (await ac.get("/orders/mine", headers={"Authorization": f"Bearer {seller_token}"})).json()
        assert any(o["id"] == order["id"] and o["order_status"] == "Active" for o in my_orders)
