import urllib.parse
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Order, OrderItem, User
from app.schemas.schemas import OrderCreateRequest, OrderResponse, OrderItemResponse
from app.repositories.base import Repository

class OrderService:
    def __init__(self, repo: Repository):
        self.repo = repo

    def generate_whatsapp_bill(self, order: Order) -> tuple[str, str]:
        """
        Builds compliant WhatsApp bill text as specified in Section 7.
        Sangh Mart
        Bill ID: SM-2026-00125
        Buyer: Ravi Kumar
        Items:
        Shirt Size M x 2 = Rs. 600
        Pant Size M x 2 = Rs. 800
        Total: Rs. 1,400
        Payment: Paid via UPI (or Total / Paid / Balance for partial)
        Date: 13-Oct-2026
        Thank you for your purchase!
        """
        lines = []
        lines.append("🕉️ *Sangh Mart*")
        lines.append(f"📄 *Bill ID:* {order.bill_no}")
        lines.append(f"👤 *Buyer:* {order.buyer.name}")
        if order.nagar:
            lines.append(f"📍 *Nagar:* {order.nagar.name}")
        lines.append("\n*Items:*")
        
        for item in order.items:
            lines.append(f"• {item.item_name} Size {item.size} x {item.quantity} = ₹{item.line_total}")
            
        lines.append(f"\n*Total:* ₹{order.total}")
        
        # Filter positive non-reversal payments
        valid_payments = [
            p for p in (order.payments or [])
            if (p.amount or 0) > 0 and (p.kind or "").lower() != "reversal"
        ]
        cash_sum = sum(p.amount for p in valid_payments if p.method and p.method.strip().lower() == "cash")
        upi_sum = sum(p.amount for p in valid_payments if p.method and p.method.strip().lower() == "upi")

        if order.payment_status == "Paid":
            if cash_sum > 0 and upi_sum == 0:
                payment_text = "Paid via Cash"
            elif upi_sum > 0 and cash_sum == 0:
                payment_text = "Paid via UPI"
            elif cash_sum > 0 and upi_sum > 0:
                payment_text = f"Paid via Cash (₹{cash_sum}) & UPI (₹{upi_sum})"
            else:
                payment_text = "Paid via Cash"
            lines.append(f"*Payment:* {payment_text}")
        else:
            lines.append(f"*Paid so far:* ₹{order.paid_amount}")
            if cash_sum > 0 and upi_sum == 0:
                lines.append(f"*Paid via:* Cash")
            elif upi_sum > 0 and cash_sum == 0:
                lines.append(f"*Paid via:* UPI")
            elif cash_sum > 0 and upi_sum > 0:
                lines.append(f"*Paid via:* Cash (₹{cash_sum}) & UPI (₹{upi_sum})")
            lines.append(f"*Balance due:* ₹{order.balance}")
            lines.append(f"*Status:* {order.payment_status}")
            
        dt_str = order.created_at.strftime("%d-%b-%Y")
        lines.append(f"📅 *Date:* {dt_str}")
        lines.append("\n_Thank you for your purchase!_")
        
        text = "\n".join(lines)
        # wa.me link with normalized phone
        clean_phone = order.buyer.phone.replace("+", "").replace(" ", "").strip()
        encoded_text = urllib.parse.quote(text)
        wa_url = f"https://wa.me/{clean_phone}?text={encoded_text}"
        return text, wa_url

    async def create_order(
        self,
        seller: User,
        order_in: OrderCreateRequest,
        idempotency_key: Optional[str] = None
    ) -> Order:
        # 1. Check idempotency: If key matches for this seller, return identical original order
        if idempotency_key:
            existing = await self.repo.get_order_by_idempotency_key(seller.id, idempotency_key)
            if existing:
                return existing

        if not order_in.items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Order must contain at least one item."
            )

        # 2. Normalize buyer phone to +91XXXXXXXXXX
        phone_raw = order_in.buyer_phone.replace("+", "").replace(" ", "").replace("-", "").strip()
        if phone_raw.startswith("91") and len(phone_raw) == 12:
            phone_normalized = f"+{phone_raw}"
        elif len(phone_raw) == 10 and phone_raw.isdigit():
            phone_normalized = f"+91{phone_raw}"
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid phone number. Must be a valid 10-digit Indian mobile number."
            )

        # 3. Upsert Buyer
        buyer = await self.repo.upsert_buyer(
            name=order_in.buyer_name,
            phone=phone_normalized,
            nagar_id=order_in.nagar_id
        )

        # 4. Process each item: recalculate price on server from database and reserve stock atomically
        server_total = 0
        order_items_to_create = []
        stock_updates_to_perform = []

        for req_item in order_in.items:
            if req_item.quantity <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Quantity must be greater than 0"
                )
            
            # Fetch item from database
            db_item = await self.repo.get_item_by_id(req_item.item_id)
            if not db_item or not db_item.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Item {req_item.item_id} is not available."
                )

            # Match size and stock
            size_obj = next((s for s in db_item.sizes if s.size == req_item.size), None)
            if not size_obj:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Size '{req_item.size}' not found for item '{db_item.name}'."
                )
            
            # Server pricing authority: Ignore client totals!
            unit_price = db_item.price
            line_total = unit_price * req_item.quantity
            server_total += line_total

            order_items_to_create.append({
                "item_id": db_item.id,
                "item_name": db_item.name,
                "size": req_item.size,
                "quantity": req_item.quantity,
                "unit_price": unit_price,
                "line_total": line_total,
                "item_size_id": size_obj.id
            })

            stock_updates_to_perform.append({
                "item_size_id": size_obj.id,
                "quantity": req_item.quantity,
                "item_name": db_item.name,
                "size": req_item.size
            })

        # 5. Check and reserve stock using atomic updates
        for su in stock_updates_to_perform:
            try:
                await self.repo.update_stock(
                    item_size_id=su["item_size_id"],
                    qty_delta=-su["quantity"],
                    movement_type="sale_reserved",
                    reason=f"Sale by {seller.name}",
                    user_id=seller.id
                )
            except ValueError as e:
                # Stock insufficient
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=str(e)
                )

        # 6. Generate sequential bill number
        bill_no = await self.repo.get_next_bill_no()

        # 7. Create Order record
        order = Order(
            bill_no=bill_no,
            idempotency_key=idempotency_key,
            seller_id=seller.id,
            buyer_id=buyer.id,
            nagar_id=order_in.nagar_id,
            total=server_total,
            paid_amount=0,
            balance=server_total,
            payment_status="Unpaid",
            order_status="Active",
            items_handed_over=False
        )
        self.repo.db.add(order)
        await self.repo.db.flush()

        # Add Order Items
        for oi in order_items_to_create:
            order_item = OrderItem(
                order_id=order.id,
                item_id=oi["item_id"],
                item_name=oi["item_name"],
                size=oi["size"],
                quantity=oi["quantity"],
                unit_price=oi["unit_price"],
                line_total=oi["line_total"]
            )
            self.repo.db.add(order_item)
        await self.repo.db.flush()

        # 8. Handle initial payment if Pay Now or Advance
        if order_in.pay_now:
            if not order_in.payment_method:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Payment method (cash or upi) required for Pay Now."
                )
            await self.repo.add_payment(
                order_id=order.id,
                amount=server_total,
                method=order_in.payment_method,
                confirmed_by=seller.id,
                kind="payment",
                utr=order_in.utr,
                screenshot_file_id=order_in.screenshot_file_id,
                note="Pay Now full payment"
            )
        elif order_in.advance_amount and order_in.advance_amount > 0:
            if order_in.advance_amount > server_total:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Advance cannot exceed total amount."
                )
            advance_method = order_in.payment_method or "cash"
            await self.repo.add_payment(
                order_id=order.id,
                amount=order_in.advance_amount,
                method=advance_method,
                confirmed_by=seller.id,
                kind="advance",
                utr=order_in.utr,
                screenshot_file_id=order_in.screenshot_file_id,
                note="Advance payment"
            )

        await self.repo.db.commit()
        # Reload with relationships
        full_order = await self.repo.get_order_by_id(order.id)
        return full_order
