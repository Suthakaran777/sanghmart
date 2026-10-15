from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.repositories.base import Repository
from app.services.order_service import OrderService
from app.schemas.schemas import (
    ItemResponse, NagarResponse, BuyerResponse,
    OrderCreateRequest, OrderResponse, OrderItemResponse
)

router = APIRouter(tags=["catalogue-and-orders"])

# ---------------- CATALOGUE ----------------
@router.get("/catalogue")
async def get_catalogue(current_user = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Provides active items, sizes, current common stock, and nagars for the order screen"""
    repo = Repository(db)
    items = await repo.list_items(active_only=True)
    nagars = await repo.list_nagars(active_only=True)
    return {
        "items": items,
        "nagars": nagars
    }

# ---------------- BUYERS ----------------
@router.get("/buyers", response_model=Optional[BuyerResponse])
async def search_buyer(phone: str, current_user = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Lookup existing buyer by phone for autofill and pending balance alerts"""
    clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "").strip()
    if clean_phone.startswith("91") and len(clean_phone) == 12:
        normalized = f"+{clean_phone}"
    elif len(clean_phone) == 10:
        normalized = f"+91{clean_phone}"
    else:
        normalized = f"+91{clean_phone}"

    repo = Repository(db)
    buyer = await repo.get_buyer_by_phone(normalized)
    if not buyer:
        return None
    
    pending_bal = await repo.get_buyer_pending_balance(buyer.id)
    return BuyerResponse(
        id=buyer.id,
        name=buyer.name,
        phone=buyer.phone,
        nagar_id=buyer.nagar_id,
        pending_balance=pending_bal
    )

# ---------------- ORDERS ----------------
def format_order_response(order, service: OrderService) -> OrderResponse:
    bill_text, wa_url = service.generate_whatsapp_bill(order)
    return OrderResponse(
        id=order.id,
        bill_no=order.bill_no,
        seller_id=order.seller_id,
        seller_name=order.seller.name if order.seller else None,
        buyer_name=order.buyer.name if order.buyer else "Unknown",
        buyer_phone=order.buyer.phone if order.buyer else "",
        nagar_name=order.nagar.name if order.nagar else None,
        total=order.total,
        paid_amount=order.paid_amount,
        balance=order.balance,
        payment_status=order.payment_status,
        order_status=order.order_status,
        cancel_reason=order.cancel_reason,
        items_handed_over=order.items_handed_over,
        created_at=order.created_at.isoformat(),
        items=[
            OrderItemResponse(
                id=item.id,
                item_id=item.item_id,
                item_name=item.item_name,
                size=item.size,
                quantity=item.quantity,
                unit_price=item.unit_price,
                line_total=item.line_total
            ) for item in order.items
        ],
        whatsapp_url=wa_url,
        bill_text=bill_text
    )

@router.post("/orders", response_model=OrderResponse)
async def create_order(
    req: OrderCreateRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    repo = Repository(db)
    service = OrderService(repo)
    order = await service.create_order(
        seller=current_user,
        order_in=req,
        idempotency_key=idempotency_key
    )
    return format_order_response(order, service)

@router.get("/orders/mine", response_model=List[OrderResponse])
async def get_my_orders(current_user = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    repo = Repository(db)
    service = OrderService(repo)
    orders = await repo.list_orders(seller_id=current_user.id)
    return [format_order_response(o, service) for o in orders]

@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order_by_id(order_id: int, current_user = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    repo = Repository(db)
    service = OrderService(repo)
    order = await repo.get_order_by_id(order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    
    # Seller isolation: A seller can only view their own orders; admin can view all
    if current_user.role != "admin" and order.seller_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this order")
        
    return format_order_response(order, service)
