from typing import List, Optional
from pydantic import BaseModel, Field

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    name: str
    username: str

class LoginRequest(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    name: str
    phone: Optional[str] = None
    username: str
    password: str
    role: str = "seller"

class UserResponse(BaseModel):
    id: int
    name: str
    phone: Optional[str] = None
    username: str
    role: str
    is_active: bool
    total_sales: Optional[int] = 0

    class Config:
        from_attributes = True

class NagarCreate(BaseModel):
    name: str

class NagarResponse(BaseModel):
    id: int
    name: str
    is_active: bool

    class Config:
        from_attributes = True

class ItemSizeCreate(BaseModel):
    size: str
    stock_qty: int = 0

class ItemSizeResponse(BaseModel):
    id: int
    item_id: int
    size: str
    stock_qty: int

    class Config:
        from_attributes = True

class ItemCreate(BaseModel):
    name: str
    price: int  # Fixed price for all sizes
    sizes: List[str] = []

class ItemResponse(BaseModel):
    id: int
    name: str
    price: int
    is_active: bool
    sizes: List[ItemSizeResponse] = []

    class Config:
        from_attributes = True

class StockUpdateRequest(BaseModel):
    item_size_id: int
    qty_delta: int  # positive to add, negative to subtract
    reason: str

class StockMovementResponse(BaseModel):
    id: int
    item_size_id: int
    qty_delta: int
    type: str
    ref_order_id: Optional[int] = None
    reason: Optional[str] = None
    user_id: Optional[int] = None

    class Config:
        from_attributes = True

class OrderItemRequest(BaseModel):
    item_id: int
    size: str
    quantity: int

class OrderCreateRequest(BaseModel):
    buyer_name: str
    buyer_phone: str  # 10 digits or normalized
    nagar_id: int
    items: List[OrderItemRequest]
    pay_now: bool = False
    payment_method: Optional[str] = None  # cash or upi
    advance_amount: Optional[int] = 0  # if adding to pending
    utr: Optional[str] = None
    screenshot_file_id: Optional[str] = None

class OrderItemResponse(BaseModel):
    id: int
    item_id: int
    item_name: str
    size: str
    quantity: int
    unit_price: int
    line_total: int

    class Config:
        from_attributes = True

class PaymentResponse(BaseModel):
    id: int
    order_id: int
    amount: int
    method: str
    utr: Optional[str] = None
    kind: str
    confirmed_by: int
    confirmed_at: str

    class Config:
        from_attributes = True

class OrderResponse(BaseModel):
    id: int
    bill_no: str
    seller_id: int
    seller_name: Optional[str] = None
    buyer_name: str
    buyer_phone: str
    nagar_name: Optional[str] = None
    total: int
    paid_amount: int
    balance: int
    payment_status: str
    order_status: str
    cancel_reason: Optional[str] = None
    items_handed_over: bool
    created_at: str
    items: List[OrderItemResponse] = []
    whatsapp_url: Optional[str] = None
    bill_text: Optional[str] = None

class BuyerResponse(BaseModel):
    id: int
    name: str
    phone: str
    nagar_id: Optional[int] = None
    pending_balance: int = 0
