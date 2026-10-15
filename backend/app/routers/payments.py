import os
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Query, Header
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_user, get_user_from_token_str
from app.repositories.base import Repository
from app.services.order_service import OrderService
from app.services.billing_service import generate_upi_qr_data_url, generate_order_pdf
from app.services.storage_service import upload_screenshot_file
from app.schemas.schemas import PaymentResponse, OrderResponse

router = APIRouter(prefix="/payments", tags=["payments"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

class CollectPaymentRequest(BaseModel):
    order_id: int
    amount: int
    method: str  # cash or upi
    utr: Optional[str] = None
    screenshot_file_id: Optional[str] = None
    note: Optional[str] = None

@router.get("/qr/{order_id}")
async def get_upi_qr_for_order(
    order_id: int,
    amount: Optional[int] = None,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns prefilled UPI QR code base64 image and UPI deep link for an order.
    Amount defaults to remaining balance if not provided.
    """
    repo = Repository(db)
    order = await repo.get_order_by_id(order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    
    if current_user.role != "admin" and order.seller_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    upi_id = await repo.get_setting("upi_id", "sanghmart@upi")
    bill_header = await repo.get_setting("bill_header", "Sangh Mart")
    
    pay_amount = amount if amount and amount > 0 else order.balance
    if pay_amount <= 0:
        pay_amount = order.total

    qr_data_url, upi_string = generate_upi_qr_data_url(
        upi_id=upi_id,
        amount=pay_amount,
        bill_no=order.bill_no,
        app_name=bill_header
    )
    return {
        "order_id": order.id,
        "bill_no": order.bill_no,
        "amount": pay_amount,
        "upi_id": upi_id,
        "upi_qr_image": qr_data_url,
        "upi_link": upi_string
    }

@router.post("/upload-proof")
async def upload_proof(
    file: UploadFile = File(...),
    current_user = Depends(get_current_user)
):
    """
    Uploads buyer's paid UPI screenshot proof (any image format).
    Stores in Cloudflare R2 if configured, or local uploads/ directory.
    """
    contents = await file.read()
    content_type = file.content_type or "image/jpeg"
    file_id = upload_screenshot_file(contents, file.filename or "proof.jpg", content_type)
    return {"file_id": file_id, "filename": file.filename}

@router.post("/collect", response_model=PaymentResponse)
async def collect_payment(
    req: CollectPaymentRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Appends payment record to an existing order.
    Seller isolation: sellers can only collect payments for their own orders; admin can collect for all.
    Validates amount does not exceed balance.
    """
    repo = Repository(db)
    order = await repo.get_order_by_id(req.order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        
    if current_user.role != "admin" and order.seller_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    try:
        payment = await repo.add_payment(
            order_id=req.order_id,
            amount=req.amount,
            method=req.method.lower(),
            confirmed_by=current_user.id,
            kind="payment",
            utr=req.utr.strip() if req.utr else None,
            screenshot_file_id=req.screenshot_file_id,
            note=req.note
        )
        await repo.add_audit(
            action="COLLECT_PAYMENT",
            entity="Payment",
            entity_id=str(payment.id),
            after=f"amount:{req.amount}, method:{req.method}",
            user_id=current_user.id
        )
        await db.commit()
        return PaymentResponse(
            id=payment.id,
            order_id=payment.order_id,
            amount=payment.amount,
            method=payment.method,
            utr=payment.utr,
            kind=payment.kind,
            confirmed_by=payment.confirmed_by,
            confirmed_at=payment.confirmed_at.isoformat()
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/pdf/{order_id}")
async def download_order_pdf(
    order_id: int,
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Generates PDF bill on demand and streams it to client. Not saved to disk.
    Accepts authentication via Authorization header or ?token= query parameter.
    """
    raw_token = token
    if not raw_token and authorization:
        if authorization.startswith("Bearer "):
            raw_token = authorization.replace("Bearer ", "").strip()
        else:
            raw_token = authorization.strip()

    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    current_user = await get_user_from_token_str(raw_token, db)

    repo = Repository(db)
    order = await repo.get_order_by_id(order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        
    if current_user.role != "admin" and order.seller_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    bill_header = await repo.get_setting("bill_header", "Sangh Mart")
    pdf_bytes = generate_order_pdf(order, bill_header=bill_header)
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Bill_{order.bill_no}.pdf"}
    )
