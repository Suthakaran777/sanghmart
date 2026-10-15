import urllib.parse
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, func, and_, or_, desc
from sqlalchemy.orm import selectinload

from app.models.models import (
    User, Nagar, Item, ItemSize, Buyer, Order, OrderItem,
    Payment, StockMovement, AuditLog, Setting
)
from app.core.config import settings

class Repository:
    """
    Data-Access Layer (Repository Pattern)
    Isolates all database read/write queries from business logic.
    Enables switching from Supabase to Neon or another database host seamlessly.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------------- USER & AUTH ----------------
    async def get_user_by_username(self, username: str) -> Optional[User]:
        stmt = select(User).where(User.username == username)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def create_user(self, name: str, username: str, password_hash: str, role: str = "seller", phone: Optional[str] = None) -> User:
        user = User(
            name=name,
            username=username,
            password_hash=password_hash,
            role=role,
            phone=phone,
            is_active=True
        )
        self.db.add(user)
        await self.db.flush()
        return user

    async def list_sellers(self) -> List[Tuple[User, int]]:
        """List all sellers along with their total confirmed sales amount"""
        stmt = select(User).where(User.role == "seller").order_by(User.id.desc())
        res = await self.db.execute(stmt)
        sellers = res.scalars().all()
        
        result = []
        for s in sellers:
            # Calculate total sales from active orders
            sum_stmt = select(func.coalesce(func.sum(Order.total), 0)).where(
                and_(Order.seller_id == s.id, Order.order_status == "Active")
            )
            sum_res = await self.db.execute(sum_stmt)
            sales_total = sum_res.scalar() or 0
            result.append((s, sales_total))
        return result

    async def update_user_status(self, user_id: int, is_active: bool) -> Optional[User]:
        user = await self.get_user_by_id(user_id)
        if user:
            user.is_active = is_active
            await self.db.flush()
        return user

    async def update_user_password(self, user_id: int, new_password_hash: str) -> Optional[User]:
        user = await self.get_user_by_id(user_id)
        if user:
            user.password_hash = new_password_hash
            await self.db.flush()
        return user

    # ---------------- NAGARS ----------------
    async def list_nagars(self, active_only: bool = True) -> List[Nagar]:
        stmt = select(Nagar)
        if active_only:
            stmt = stmt.where(Nagar.is_active == True)
        stmt = stmt.order_by(Nagar.name.asc())
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def create_nagar(self, name: str) -> Nagar:
        nagar = Nagar(name=name.strip(), is_active=True)
        self.db.add(nagar)
        await self.db.flush()
        return nagar

    async def get_nagar_by_id(self, nagar_id: int) -> Optional[Nagar]:
        stmt = select(Nagar).where(Nagar.id == nagar_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    # ---------------- ITEMS & SIZES & STOCK ----------------
    async def list_items(self, active_only: bool = True) -> List[Item]:
        stmt = select(Item).options(selectinload(Item.sizes))
        if active_only:
            stmt = stmt.where(Item.is_active == True)
        stmt = stmt.order_by(Item.id.asc())
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_item_by_id(self, item_id: int) -> Optional[Item]:
        stmt = select(Item).options(selectinload(Item.sizes)).where(Item.id == item_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_item_by_name(self, name: str) -> Optional[Item]:
        stmt = select(Item).options(selectinload(Item.sizes)).where(Item.name == name)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def create_item(self, name: str, price: int, sizes: List[str]) -> Item:
        item = Item(name=name.strip(), price=price, is_active=True)
        self.db.add(item)
        await self.db.flush()
        
        for s in sizes:
            item_size = ItemSize(item_id=item.id, size=s.strip(), stock_qty=0)
            self.db.add(item_size)
        await self.db.flush()
        return item

    async def get_item_size(self, item_id: int, size: str) -> Optional[ItemSize]:
        stmt = select(ItemSize).where(and_(ItemSize.item_id == item_id, ItemSize.size == size))
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_item_size_by_id(self, item_size_id: int) -> Optional[ItemSize]:
        stmt = select(ItemSize).where(ItemSize.id == item_size_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def update_stock(self, item_size_id: int, qty_delta: int, movement_type: str, reason: str, user_id: Optional[int] = None, ref_order_id: Optional[int] = None) -> ItemSize:
        """
        Updates stock using strict atomic row verification.
        qty_delta can be positive (add/return) or negative (sale reservation).
        """
        stmt = select(ItemSize).where(ItemSize.id == item_size_id).with_for_update()
        res = await self.db.execute(stmt)
        item_size = res.scalar_one_or_none()
        if not item_size:
            raise ValueError(f"ItemSize {item_size_id} not found")
        
        new_qty = item_size.stock_qty + qty_delta
        if new_qty < 0:
            raise ValueError(f"Insufficient stock for {item_size.size}. Available: {item_size.stock_qty}, requested delta: {qty_delta}")
        
        item_size.stock_qty = new_qty
        
        # Write to immutable stock movements ledger
        movement = StockMovement(
            item_size_id=item_size_id,
            qty_delta=qty_delta,
            type=movement_type,
            ref_order_id=ref_order_id,
            reason=reason,
            user_id=user_id
        )
        self.db.add(movement)
        await self.db.flush()
        return item_size

    async def list_stock_movements(self, limit: int = 100) -> List[StockMovement]:
        stmt = select(StockMovement).order_by(StockMovement.id.desc()).limit(limit)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    # ---------------- BUYERS ----------------
    async def get_buyer_by_phone(self, phone: str) -> Optional[Buyer]:
        stmt = select(Buyer).where(Buyer.phone == phone)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def upsert_buyer(self, name: str, phone: str, nagar_id: Optional[int] = None) -> Buyer:
        buyer = await self.get_buyer_by_phone(phone)
        if buyer:
            buyer.name = name.strip()
            if nagar_id:
                buyer.nagar_id = nagar_id
        else:
            buyer = Buyer(name=name.strip(), phone=phone, nagar_id=nagar_id)
            self.db.add(buyer)
        await self.db.flush()
        return buyer

    async def get_buyer_pending_balance(self, buyer_id: int) -> int:
        stmt = select(func.coalesce(func.sum(Order.balance), 0)).where(
            and_(Order.buyer_id == buyer_id, Order.order_status == "Active", Order.balance > 0)
        )
        res = await self.db.execute(stmt)
        return res.scalar() or 0

    # ---------------- ORDERS & BILLING ----------------
    async def get_next_bill_no(self) -> str:
        """Sequential bill number format SM-2026-00001"""
        prefix = settings.BILL_PREFIX
        year = settings.BILL_YEAR
        pattern = f"{prefix}-{year}-%"
        stmt = select(func.count(Order.id)).where(Order.bill_no.like(pattern))
        res = await self.db.execute(stmt)
        count = (res.scalar() or 0) + 1
        return f"{prefix}-{year}-{count:05d}"

    async def get_order_by_idempotency_key(self, seller_id: int, key: str) -> Optional[Order]:
        if not key:
            return None
        stmt = select(Order).options(
            selectinload(Order.items),
            selectinload(Order.payments),
            selectinload(Order.buyer),
            selectinload(Order.nagar),
            selectinload(Order.seller)
        ).where(and_(Order.seller_id == seller_id, Order.idempotency_key == key))
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_order_by_id(self, order_id: int) -> Optional[Order]:
        stmt = select(Order).options(
            selectinload(Order.items),
            selectinload(Order.payments),
            selectinload(Order.buyer),
            selectinload(Order.nagar),
            selectinload(Order.seller)
        ).where(Order.id == order_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def list_orders(
        self,
        seller_id: Optional[int] = None,
        payment_status: Optional[str] = None,
        only_pending: bool = False,
        limit: int = 100
    ) -> List[Order]:
        stmt = select(Order).options(
            selectinload(Order.items),
            selectinload(Order.payments),
            selectinload(Order.buyer),
            selectinload(Order.nagar),
            selectinload(Order.seller)
        )
        conditions = []
        if seller_id is not None:
            conditions.append(Order.seller_id == seller_id)
        if payment_status:
            conditions.append(Order.payment_status == payment_status)
        if only_pending:
            conditions.append(Order.order_status == "Active")
            conditions.append(Order.balance > 0)
        
        if conditions:
            stmt = stmt.where(and_(*conditions))
        
        stmt = stmt.order_by(Order.id.desc()).limit(limit)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    # ---------------- PAYMENTS ----------------
    async def add_payment(
        self,
        order_id: int,
        amount: int,
        method: str,
        confirmed_by: int,
        kind: str = "payment",
        utr: Optional[str] = None,
        screenshot_file_id: Optional[str] = None,
        note: Optional[str] = None
    ) -> Payment:
        # Check if UTR is provided and duplicate
        if utr:
            stmt = select(Payment).where(Payment.utr == utr)
            dup = (await self.db.execute(stmt)).scalar_one_or_none()
            if dup:
                raise ValueError(f"Payment with UTR '{utr}' has already been recorded.")

        order = await self.get_order_by_id(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        if order.order_status != "Active":
            raise ValueError("Cannot add payment to a cancelled order")
        if amount <= 0:
            raise ValueError("Payment amount must be greater than zero")
        if amount > order.balance:
            raise ValueError(f"Payment of ₹{amount} exceeds remaining balance of ₹{order.balance}")

        payment = Payment(
            order_id=order_id,
            amount=amount,
            method=method,
            utr=utr,
            screenshot_file_id=screenshot_file_id,
            confirmed_by=confirmed_by,
            kind=kind,
            note=note
        )
        self.db.add(payment)
        if order.payments is not None and payment not in order.payments:
            order.payments.append(payment)
        
        # Update order amounts & payment status
        order.paid_amount += amount
        order.balance = order.total - order.paid_amount
        if order.balance == 0:
            order.payment_status = "Paid"
        else:
            order.payment_status = "Partial"
            
        await self.db.flush()
        return payment

    # ---------------- AUDIT LOG & SETTINGS ----------------
    async def add_audit(self, action: str, entity: str, entity_id: str, before: str = "", after: str = "", user_id: Optional[int] = None, reason: str = ""):
        log = AuditLog(
            user_id=user_id,
            action=action,
            entity=entity,
            entity_id=str(entity_id),
            before=before,
            after=after,
            reason=reason
        )
        self.db.add(log)
        await self.db.flush()

    async def get_setting(self, key: str, default: str = "") -> str:
        stmt = select(Setting).where(Setting.key == key)
        res = await self.db.execute(stmt)
        setting = res.scalar_one_or_none()
        return setting.value if setting else default

    async def set_setting(self, key: str, value: str):
        stmt = select(Setting).where(Setting.key == key)
        res = await self.db.execute(stmt)
        setting = res.scalar_one_or_none()
        if setting:
            setting.value = value
        else:
            self.db.add(Setting(key=key, value=value))
        await self.db.flush()
