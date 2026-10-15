from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Boolean, ForeignKey, DateTime, Text, BigInteger
)
from sqlalchemy.orm import relationship
from app.core.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    role = Column(String(20), nullable=False, default="seller")  # admin, seller
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

class Nagar(Base):
    __tablename__ = "nagars"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

class Item(Base):
    __tablename__ = "items"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)  # Shirt, Pant, Cap, Belt, Shoe, Socks
    price = Column(Integer, nullable=False)  # Price in INR (or Paise if preferred; spec says fixed integer price)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    
    sizes = relationship("ItemSize", back_populates="item", cascade="all, delete-orphan", lazy="selectin")

class ItemSize(Base):
    __tablename__ = "item_sizes"
    
    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False, index=True)
    size = Column(String(50), nullable=False)  # e.g. 36, 38, 40, S, M, L, etc.
    stock_qty = Column(Integer, default=0, nullable=False)
    
    item = relationship("Item", back_populates="sizes")

class Buyer(Base):
    __tablename__ = "buyers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    phone = Column(String(20), unique=True, index=True, nullable=False)  # Normalized e.g. +91XXXXXXXXXX
    nagar_id = Column(Integer, ForeignKey("nagars.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    
    nagar = relationship("Nagar")

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    bill_no = Column(String(50), unique=True, index=True, nullable=False)
    idempotency_key = Column(String(100), index=True, nullable=True)
    seller_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    buyer_id = Column(Integer, ForeignKey("buyers.id"), nullable=False, index=True)
    nagar_id = Column(Integer, ForeignKey("nagars.id"), nullable=True)
    
    # Financial fields in integers
    total = Column(Integer, nullable=False, default=0)
    paid_amount = Column(Integer, nullable=False, default=0)
    balance = Column(Integer, nullable=False, default=0)
    
    # States: Unpaid, Partial, Paid
    payment_status = Column(String(20), nullable=False, default="Unpaid")
    # States: Active, Cancelled
    order_status = Column(String(20), nullable=False, default="Active")
    cancel_reason = Column(String(255), nullable=True)
    
    items_handed_over = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    
    seller = relationship("User", lazy="selectin")
    buyer = relationship("Buyer", lazy="selectin")
    nagar = relationship("Nagar", lazy="selectin")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan", lazy="selectin")
    payments = relationship("Payment", back_populates="order", cascade="all, delete-orphan", lazy="selectin")

class OrderItem(Base):
    __tablename__ = "order_items"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    item_name = Column(String(100), nullable=False)
    size = Column(String(50), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Integer, nullable=False)  # snapshot
    line_total = Column(Integer, nullable=False)  # snapshot
    
    order = relationship("Order", back_populates="items")
    item = relationship("Item")

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    method = Column(String(20), nullable=False)  # cash, upi
    utr = Column(String(50), nullable=True, index=True)
    screenshot_file_id = Column(String(255), nullable=True)
    confirmed_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    confirmed_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    kind = Column(String(20), nullable=False, default="payment")  # advance, payment, reversal
    note = Column(String(255), nullable=True)
    
    order = relationship("Order", back_populates="payments")
    confirmed_by_user = relationship("User")

class StockMovement(Base):
    __tablename__ = "stock_movements"
    
    id = Column(Integer, primary_key=True, index=True)
    item_size_id = Column(Integer, ForeignKey("item_sizes.id"), nullable=False, index=True)
    qty_delta = Column(Integer, nullable=False)  # positive for addition/return, negative for sale
    type = Column(String(50), nullable=False)  # opening, adjustment, sale_reserved, order_cancelled
    ref_order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    reason = Column(String(255), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

class AuditLog(Base):
    __tablename__ = "audit_log"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    entity = Column(String(100), nullable=False)
    entity_id = Column(String(100), nullable=True)
    before = Column(Text, nullable=True)
    after = Column(Text, nullable=True)
    reason = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

class Setting(Base):
    __tablename__ = "settings"
    
    key = Column(String(100), primary_key=True, index=True)
    value = Column(Text, nullable=False)
