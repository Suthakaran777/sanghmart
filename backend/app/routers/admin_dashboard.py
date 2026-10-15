import io
import csv
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, and_, or_, desc
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_admin, get_password_hash
from app.models.models import (
    User, Order, OrderItem, Payment, Item, ItemSize, Nagar, Buyer, StockMovement, AuditLog, Setting
)
from app.repositories.base import Repository
from app.services.order_service import OrderService
from app.services.billing_service import generate_order_pdf
from app.routers.orders import format_order_response
from app.schemas.schemas import (
    UserResponse, UserCreate, NagarResponse, NagarCreate,
    ItemResponse, ItemCreate, StockUpdateRequest, StockMovementResponse,
    OrderResponse
)

router = APIRouter(prefix="/admin", tags=["admin-dashboard"])

# ---------------- 1. DASHBOARD OVERVIEW METRICS ----------------
@router.get("/dashboard-metrics")
async def get_dashboard_metrics(
    admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Every total is calculated by the server from saved records:
    - Total Orders count (all time & today)
    - Total sales amount (Active orders)
    - Cash collected (from Payments ledger)
    - UPI collected (from Payments ledger)
    - Total pending balance across all active orders
    - Count of orders currently pending
    - Cancelled orders count
    """
    now = datetime.now(timezone.utc)
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)

    # 1. Active Orders Totals
    active_stmt = select(
        func.count(Order.id).label("total_orders"),
        func.coalesce(func.sum(Order.total), 0).label("total_sales"),
        func.coalesce(func.sum(Order.balance), 0).label("pending_balance")
    ).where(Order.order_status == "Active")
    active_res = (await db.execute(active_stmt)).one()

    # Today's Orders
    today_stmt = select(func.count(Order.id)).where(
        and_(Order.order_status == "Active", Order.created_at >= today_start)
    )
    today_count = (await db.execute(today_stmt)).scalar() or 0

    # Cancelled Orders
    cancelled_stmt = select(func.count(Order.id)).where(Order.order_status == "Cancelled")
    cancelled_count = (await db.execute(cancelled_stmt)).scalar() or 0

    # Pending Orders count (Active orders with balance > 0)
    pending_count_stmt = select(func.count(Order.id)).where(
        and_(Order.order_status == "Active", Order.balance > 0)
    )
    pending_count = (await db.execute(pending_count_stmt)).scalar() or 0

    # 2. Payments totals by method (from append-only payments table for Active orders)
    cash_stmt = select(func.coalesce(func.sum(Payment.amount), 0)).join(Order).where(
        and_(Order.order_status == "Active", Payment.method == "cash")
    )
    cash_total = (await db.execute(cash_stmt)).scalar() or 0

    upi_stmt = select(func.coalesce(func.sum(Payment.amount), 0)).join(Order).where(
        and_(Order.order_status == "Active", Payment.method == "upi")
    )
    upi_total = (await db.execute(upi_stmt)).scalar() or 0

    return {
        "total_orders": active_res.total_orders,
        "today_orders": today_count,
        "cancelled_orders": cancelled_count,
        "total_sales_value": active_res.total_sales,
        "cash_total": cash_total,
        "upi_total": upi_total,
        "total_collected": cash_total + upi_total,
        "pending_balance": active_res.pending_balance,
        "pending_orders_count": pending_count
    }

# ---------------- 2. ITEM-BY-SIZE SALES AGGREGATION & LOW-STOCK ----------------
@router.get("/reports/item-by-size")
async def get_item_by_size_report(
    admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Item-by-size sales table matches sum of Active order items.
    Also returns remaining common stock and highlights low-stock (< 5).
    """
    repo = Repository(db)
    items = await repo.list_items(active_only=False)

    # Aggregate quantities sold per item_id and size
    sales_stmt = select(
        OrderItem.item_id,
        OrderItem.size,
        func.sum(OrderItem.quantity).label("sold_qty"),
        func.sum(OrderItem.line_total).label("sold_revenue")
    ).join(Order).where(Order.order_status == "Active").group_by(OrderItem.item_id, OrderItem.size)
    sales_res = await db.execute(sales_stmt)
    
    sales_map = {}
    for row in sales_res.all():
        sales_map[(row.item_id, row.size)] = {
            "sold_qty": row.sold_qty,
            "sold_revenue": row.sold_revenue
        }

    report = []
    for item in items:
        item_sizes_data = []
        for s in item.sizes:
            sold_info = sales_map.get((item.id, s.size), {"sold_qty": 0, "sold_revenue": 0})
            item_sizes_data.append({
                "item_size_id": s.id,
                "size": s.size,
                "available_stock": s.stock_qty,
                "is_low_stock": s.stock_qty <= 5,
                "sold_qty": sold_info["sold_qty"],
                "sold_revenue": sold_info["sold_revenue"]
            })
        report.append({
            "item_id": item.id,
            "item_name": item.name,
            "price": item.price,
            "sizes": item_sizes_data
        })

    return report

# ---------------- 3. NAGAR-WISE SALES REPORT ----------------
@router.get("/reports/nagar-wise")
async def get_nagar_wise_report(
    admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Aggregates sales, orders count, and pending balances by Nagar"""
    stmt = select(
        Nagar.id,
        Nagar.name,
        func.count(Order.id).label("order_count"),
        func.coalesce(func.sum(Order.total), 0).label("total_sales"),
        func.coalesce(func.sum(Order.paid_amount), 0).label("total_paid"),
        func.coalesce(func.sum(Order.balance), 0).label("total_balance")
    ).outerjoin(Order, and_(Order.nagar_id == Nagar.id, Order.order_status == "Active")).group_by(Nagar.id, Nagar.name).order_by(desc("total_sales"))
    res = await db.execute(stmt)
    
    return [
        {
            "nagar_id": r.id,
            "nagar_name": r.name,
            "order_count": r.order_count,
            "total_sales": r.total_sales,
            "total_paid": r.total_paid,
            "total_balance": r.total_balance
        }
        for r in res.all()
    ]

# ---------------- 4. ALL ORDERS & ALL BILLS WITH SEARCH ----------------
@router.get("/orders", response_model=List[OrderResponse])
async def list_all_orders(
    search: Optional[str] = None,
    nagar_id: Optional[int] = None,
    seller_id: Optional[int] = None,
    payment_status: Optional[str] = None,
    order_status: Optional[str] = None,
    only_pending: bool = False,
    admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Admin view of all orders and bills with filtering and text search"""
    repo = Repository(db)
    service = OrderService(repo)

    stmt = select(Order).options(
        selectinload(Order.items),
        selectinload(Order.payments),
        selectinload(Order.buyer),
        selectinload(Order.nagar),
        selectinload(Order.seller)
    )

    conditions = []
    if only_pending:
        conditions.append(Order.order_status == "Active")
        conditions.append(Order.balance > 0)
    if payment_status:
        conditions.append(Order.payment_status == payment_status)
    if order_status:
        conditions.append(Order.order_status == order_status)
    if nagar_id:
        conditions.append(Order.nagar_id == nagar_id)
    if seller_id:
        conditions.append(Order.seller_id == seller_id)

    if search:
        s = f"%{search.strip()}%"
        conditions.append(
            or_(
                Order.bill_no.ilike(s),
                Order.buyer.has(Buyer.name.ilike(s)),
                Order.buyer.has(Buyer.phone.ilike(s))
            )
        )

    if conditions:
        stmt = stmt.where(and_(*conditions))

    stmt = stmt.order_by(Order.id.desc()).limit(300)
    res = await db.execute(stmt)
    orders = res.scalars().all()
    return [format_order_response(o, service) for o in orders]

# ---------------- 5. CANCEL ORDER (WITH REASON & AUTOMATIC STOCK RETURN) ----------------
@router.post("/orders/{order_id}/cancel")
async def cancel_order(
    order_id: int,
    payload: dict,  # {"reason": "Customer cancelled"}
    admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Admin only: Cancelling an order automatically returns reserved stock to the common pool.
    Records a refund/cancellation note for accounting in the audit ledger.
    """
    reason = payload.get("reason", "Cancelled by Admin").strip()
    if not reason:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cancellation reason is required.")

    repo = Repository(db)
    order = await repo.get_order_by_id(order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.order_status == "Cancelled":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order is already cancelled")

    # 1. Return stock for each item in the order
    for it in order.items:
        item_size = await repo.get_item_size(it.item_id, it.size)
        if item_size:
            await repo.update_stock(
                item_size_id=item_size.id,
                qty_delta=it.quantity,  # positive returns stock
                movement_type="order_cancelled",
                reason=f"Order {order.bill_no} cancelled: {reason}",
                user_id=admin.id,
                ref_order_id=order.id
            )

    # 2. If any money was paid, record refund note in payments ledger
    if order.paid_amount > 0:
        refund_payment = Payment(
            order_id=order.id,
            amount=-order.paid_amount,
            method="refund",
            confirmed_by=admin.id,
            kind="reversal",
            note=f"Refund due to cancellation: {reason}"
        )
        db.add(refund_payment)

    # 3. Mark order as Cancelled
    order.order_status = "Cancelled"
    order.cancel_reason = reason

    # 4. Audit log
    await repo.add_audit(
        action="CANCEL_ORDER",
        entity="Order",
        entity_id=str(order.id),
        before=f"total:{order.total}, paid:{order.paid_amount}",
        after="Cancelled",
        reason=reason,
        user_id=admin.id
    )

    await db.commit()
    return {"message": f"Order {order.bill_no} cancelled and stock returned successfully."}

# ---------------- 5b. REVERT CANCELLED ORDER (ADMIN ONLY) ----------------
@router.post("/orders/{order_id}/revert")
async def revert_order(
    order_id: int,
    payload: Optional[dict] = None,
    admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Admin only: Revert a cancelled order back to Active.
    1. Checks if the order is currently Cancelled.
    2. Validates available stock for all items in the order.
    3. Atomically reserves stock again (-quantity delta).
    4. Removes any refund/reversal payment recorded during cancellation.
    5. Sets order.order_status = 'Active' and clears cancel_reason.
    6. Writes an audit log entry.
    """
    reason = (payload.get("reason", "Order restored by admin") if payload else "Order restored by admin").strip()

    repo = Repository(db)
    order = await repo.get_order_by_id(order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.order_status != "Cancelled":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Order is not cancelled (current status: {order.order_status}).")

    # 1. Check stock availability for all items first
    for it in order.items:
        item_size = await repo.get_item_size(it.item_id, it.size)
        if not item_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot revert order: Size '{it.size}' for '{it.item_name}' was not found."
            )
        if item_size.stock_qty < it.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot revert order: Insufficient stock for {it.item_name} (Size {it.size}). Available: {item_size.stock_qty}, Needed: {it.quantity}."
            )

    # 2. Re-reserve stock
    for it in order.items:
        item_size = await repo.get_item_size(it.item_id, it.size)
        await repo.update_stock(
            item_size_id=item_size.id,
            qty_delta=-it.quantity,
            movement_type="order_reverted",
            reason=f"Order {order.bill_no} restored/reverted: {reason}",
            user_id=admin.id,
            ref_order_id=order.id
        )

    # 3. Remove refund reversal entries
    for p in list(order.payments):
        if p.method == "refund" or p.kind == "reversal":
            await db.delete(p)

    # 4. Mark order as Active
    prev_reason = order.cancel_reason
    order.order_status = "Active"
    order.cancel_reason = None

    # 5. Audit log
    await repo.add_audit(
        action="REVERT_ORDER",
        entity="Order",
        entity_id=str(order.id),
        before=f"Cancelled (Reason: {prev_reason})",
        after="Active (Reinstated)",
        reason=reason,
        user_id=admin.id
    )

    await db.commit()
    await db.refresh(order)

    service = OrderService(repo)
    return format_order_response(order, service)

# ---------------- 6. EXCEL (.XLSX) DATA EXPORT ----------------
@router.get("/export/excel")
async def export_orders_excel(
    token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    from app.core.security import jwt, settings
    from app.repositories.base import Repository
    admin_user = None
    if token:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            username = payload.get("sub")
            if username:
                repo = Repository(db)
                u = await repo.get_user_by_username(username)
                if u and u.is_active and u.role == "admin":
                    admin_user = u
        except Exception:
            pass
    if not admin_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated as admin")
    """
    Generates a complete, professionally formatted Excel workbook (.xlsx) containing:
    - Bill No
    - Date & Time
    - Nagar (Dedicated column)
    - Buyer Name
    - Buyer Phone
    - Seller Name
    - Items & Sizes Ordered
    - Total Order Value (₹)
    - Cash Collected (₹) (Dedicated column)
    - UPI Collected (₹) (Dedicated column)
    - Total Paid Amount (₹)
    - Balance Due (₹)
    - Payment Status
    - Order Status
    - UTR Numbers / Reference
    - Handed Over
    """
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    stmt = select(Order).options(
        selectinload(Order.items),
        selectinload(Order.payments),
        selectinload(Order.buyer),
        selectinload(Order.nagar),
        selectinload(Order.seller)
    ).order_by(Order.id.asc())
    res = await db.execute(stmt)
    orders = res.scalars().all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Orders & Collections"
    ws.views.sheetView[0].showGridLines = True

    # Styling definitions
    header_fill = PatternFill(start_color="D9531E", end_color="D9531E", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    bold_font = Font(name="Calibri", size=11, bold=True)
    regular_font = Font(name="Calibri", size=10)
    center_align = Alignment(horizontal="center", vertical="center")
    left_align = Alignment(horizontal="left", vertical="center")
    right_align = Alignment(horizontal="right", vertical="center")
    thin_border = Border(
        left=Side(style='thin', color='E2E8F0'),
        right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='E2E8F0'),
        bottom=Side(style='thin', color='E2E8F0')
    )

    headers = [
        "Bill No",
        "Order Date",
        "Nagar",
        "Buyer Name",
        "Buyer WhatsApp Phone",
        "Seller Name",
        "Items Ordered & Sizes",
        "Total Value (Rs.)",
        "Cash Collected (Rs.)",
        "UPI Collected (Rs.)",
        "Total Paid (Rs.)",
        "Balance Due (Rs.)",
        "Payment Status",
        "Order Status",
        "UPI UTR Reference",
        "Items Handed Over"
    ]

    ws.append(headers)
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align
        cell.border = thin_border
    ws.row_dimensions[1].height = 28

    total_sales_sum = 0
    total_cash_sum = 0
    total_upi_sum = 0
    total_paid_sum = 0
    total_balance_sum = 0

    row_num = 2
    for o in orders:
        # Separate cash and UPI collections from payments ledger
        cash_for_order = sum(p.amount for p in o.payments if p.method.lower() == "cash")
        upi_for_order = sum(p.amount for p in o.payments if p.method.lower() == "upi")
        utrs_list = [p.utr for p in o.payments if p.utr]
        utr_str = ", ".join(utrs_list) if utrs_list else "-"

        items_str = "; ".join([f"{it.item_name} (Size {it.size}) x {it.quantity}" for it in o.items])
        nagar_str = o.nagar.name if o.nagar else "N/A"
        date_str = o.created_at.strftime("%d-%b-%Y %I:%M %p")
        handed_over_str = "Yes" if o.items_handed_over else "No"

        row_data = [
            o.bill_no,
            date_str,
            nagar_str,
            o.buyer.name if o.buyer else "Unknown",
            o.buyer.phone if o.buyer else "",
            o.seller.name if o.seller else "",
            items_str,
            o.total,
            cash_for_order,
            upi_for_order,
            o.paid_amount,
            o.balance,
            o.payment_status,
            o.order_status,
            utr_str,
            handed_over_str
        ]

        ws.append(row_data)

        # Track totals for active orders
        if o.order_status == "Active":
            total_sales_sum += o.total
            total_cash_sum += cash_for_order
            total_upi_sum += upi_for_order
            total_paid_sum += o.paid_amount
            total_balance_sum += o.balance

        # Apply cell formats
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=row_num, column=col_idx)
            cell.font = regular_font
            cell.border = thin_border
            if col_idx in [1, 2, 13, 14, 16]:
                cell.alignment = center_align
            elif col_idx in [8, 9, 10, 11, 12]:
                cell.alignment = right_align
                cell.number_format = '#,##0'
            else:
                cell.alignment = left_align

        ws.row_dimensions[row_num].height = 20
        row_num += 1

    # Append Summary / Totals Row
    summary_row = [
        "TOTAL (Active Orders)", "", "", "", "", "", "",
        total_sales_sum,
        total_cash_sum,
        total_upi_sum,
        total_paid_sum,
        total_balance_sum,
        "", "", "", ""
    ]
    ws.append(summary_row)
    summary_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=row_num, column=col_idx)
        cell.font = bold_font
        cell.fill = summary_fill
        cell.border = thin_border
        if col_idx in [8, 9, 10, 11, 12]:
            cell.alignment = right_align
            cell.number_format = '#,##0'
        elif col_idx == 1:
            cell.alignment = left_align
    ws.row_dimensions[row_num].height = 24

    # Auto-adjust column widths
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val_str = str(cell.value or '')
            if len(val_str) > max_len:
                max_len = len(val_str)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"SanghMart_Orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# ---------------- 7. ITEM-BY-SIZE SALES EXCEL EXPORT ----------------
@router.get("/export/excel-items")
async def export_item_sales_excel(
    token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Excel report for Item Sales:
    - Item Name, Size, Units Sold, Item Unit Price (Rs.), Revenue (Rs.)
    - Excludes available stock (only visible in app)
    - Total summary row at the end with overall count and revenue
    """
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    from app.core.security import jwt, settings
    admin_user = None
    if token:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            username = payload.get("sub")
            if username:
                repo = Repository(db)
                u = await repo.get_user_by_username(username)
                if u and u.is_active and u.role == "admin":
                    admin_user = u
        except Exception:
            pass
    if not admin_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated as admin")

    repo = Repository(db)
    items = await repo.list_items(active_only=False)

    sales_stmt = select(
        OrderItem.item_id,
        OrderItem.size,
        func.sum(OrderItem.quantity).label("sold_qty"),
        func.sum(OrderItem.line_total).label("sold_revenue")
    ).join(Order).where(Order.order_status == "Active").group_by(OrderItem.item_id, OrderItem.size)
    sales_res = await db.execute(sales_stmt)
    
    sales_map = {}
    for row in sales_res.all():
        sales_map[(row.item_id, row.size)] = {
            "sold_qty": row.sold_qty,
            "sold_revenue": row.sold_revenue
        }

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Item Sales Breakdown"
    ws.views.sheetView[0].showGridLines = True

    header_fill = PatternFill(start_color="D9531E", end_color="D9531E", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    bold_font = Font(name="Calibri", size=11, bold=True)
    regular_font = Font(name="Calibri", size=10)
    thin_border = Border(
        left=Side(style='thin', color='E2E8F0'),
        right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='E2E8F0'),
        bottom=Side(style='thin', color='E2E8F0')
    )

    headers = ["Item Name", "Size", "Price (Rs.)", "Quantity Sold", "Total Revenue (Rs.)"]
    ws.append(headers)
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border
    ws.row_dimensions[1].height = 26

    total_qty_sold = 0
    total_rev = 0
    row_num = 2

    for item in items:
        item_total_qty = 0
        item_total_rev = 0
        for s in item.sizes:
            sold_info = sales_map.get((item.id, s.size), {"sold_qty": 0, "sold_revenue": 0})
            sqty = sold_info["sold_qty"] or 0
            srev = sold_info["sold_revenue"] or 0
            item_total_qty += sqty
            item_total_rev += srev
            total_qty_sold += sqty
            total_rev += srev

            ws.append([item.name, s.size, item.price, sqty, srev])
            for col_idx in range(1, len(headers) + 1):
                cell = ws.cell(row=row_num, column=col_idx)
                cell.font = regular_font
                cell.border = thin_border
                if col_idx in [1, 2]:
                    cell.alignment = Alignment(horizontal="left", vertical="center")
                else:
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                    cell.number_format = '#,##0'
            row_num += 1

        # Item subtotal row
        item_subtotal_fill = PatternFill(start_color="FFF7ED", end_color="FFF7ED", fill_type="solid")
        ws.append([f"Total {item.name} Sold", "", item.price, item_total_qty, item_total_rev])
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=row_num, column=col_idx)
            cell.font = Font(name="Calibri", size=10, bold=True, color="C2410C")
            cell.fill = item_subtotal_fill
            cell.border = thin_border
            if col_idx in [1, 2]:
                cell.alignment = Alignment(horizontal="left", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="right", vertical="center")
                cell.number_format = '#,##0'
        row_num += 1

    # Overall Summary Row
    ws.append(["GRAND TOTAL", "", "", total_qty_sold, total_rev])
    summary_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=row_num, column=col_idx)
        cell.font = bold_font
        cell.fill = summary_fill
        cell.border = thin_border
        if col_idx in [1, 2]:
            cell.alignment = Alignment(horizontal="left", vertical="center")
        else:
            cell.alignment = Alignment(horizontal="right", vertical="center")
            cell.number_format = '#,##0'
    ws.row_dimensions[row_num].height = 24

    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        ws.column_dimensions[get_column_letter(col[0].column)].width = max(max_len + 4, 14)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    filename = f"SanghMart_ItemSales_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# ---------------- 8. NAGAR-WISE SALES EXCEL EXPORT ----------------
@router.get("/export/excel-nagars")
async def export_nagar_sales_excel(
    token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Excel report for Nagar-wise sales distribution:
    - Nagar Name, Orders Count, Sales (Rs.), Paid (Rs.), Pending (Rs.)
    - Summary row at the bottom with all column totals
    """
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    from app.core.security import jwt, settings
    admin_user = None
    if token:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            username = payload.get("sub")
            if username:
                repo = Repository(db)
                u = await repo.get_user_by_username(username)
                if u and u.is_active and u.role == "admin":
                    admin_user = u
        except Exception:
            pass
    if not admin_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated as admin")

    stmt = select(
        Nagar.id,
        Nagar.name,
        func.count(Order.id).label("order_count"),
        func.coalesce(func.sum(Order.total), 0).label("total_sales"),
        func.coalesce(func.sum(Order.paid_amount), 0).label("total_paid"),
        func.coalesce(func.sum(Order.balance), 0).label("total_balance")
    ).outerjoin(Order, and_(Order.nagar_id == Nagar.id, Order.order_status == "Active")).group_by(Nagar.id, Nagar.name).order_by(desc("total_sales"))
    res = await db.execute(stmt)
    rows = res.all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Nagar-wise Sales"
    ws.views.sheetView[0].showGridLines = True

    header_fill = PatternFill(start_color="D9531E", end_color="D9531E", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    bold_font = Font(name="Calibri", size=11, bold=True)
    regular_font = Font(name="Calibri", size=10)
    thin_border = Border(
        left=Side(style='thin', color='E2E8F0'),
        right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='E2E8F0'),
        bottom=Side(style='thin', color='E2E8F0')
    )

    headers = ["Nagar Name", "Orders", "Sales (Rs.)", "Paid (Rs.)", "Pending Balance (Rs.)"]
    ws.append(headers)
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border
    ws.row_dimensions[1].height = 26

    tot_orders = 0
    tot_sales = 0
    tot_paid = 0
    tot_bal = 0
    row_num = 2

    for r in rows:
        tot_orders += r.order_count
        tot_sales += r.total_sales
        tot_paid += r.total_paid
        tot_bal += r.total_balance

        ws.append([r.name, r.order_count, r.total_sales, r.total_paid, r.total_balance])
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=row_num, column=col_idx)
            cell.font = regular_font
            cell.border = thin_border
            if col_idx == 1:
                cell.alignment = Alignment(horizontal="left", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="right", vertical="center")
                cell.number_format = '#,##0'
        row_num += 1

    # Totals summary row
    ws.append(["TOTAL", tot_orders, tot_sales, tot_paid, tot_bal])
    summary_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=row_num, column=col_idx)
        cell.font = bold_font
        cell.fill = summary_fill
        cell.border = thin_border
        if col_idx == 1:
            cell.alignment = Alignment(horizontal="left", vertical="center")
        else:
            cell.alignment = Alignment(horizontal="right", vertical="center")
            cell.number_format = '#,##0'
    ws.row_dimensions[row_num].height = 24

    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        ws.column_dimensions[get_column_letter(col[0].column)].width = max(max_len + 4, 16)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    filename = f"SanghMart_NagarSales_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# ---------------- 9. CSV DATA EXPORT & DAILY BACKUP ----------------
@router.get("/export/csv")
async def export_orders_csv(
    token: Optional[str] = Query(None),
    admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Generates a full daily CSV export of all orders for backup and accounting.
    """
    stmt = select(Order).options(
        selectinload(Order.items),
        selectinload(Order.payments),
        selectinload(Order.buyer),
        selectinload(Order.nagar),
        selectinload(Order.seller)
    ).order_by(Order.id.asc())
    res = await db.execute(stmt)
    orders = res.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Bill No", "Date", "Nagar", "Buyer Name", "Buyer Phone",
        "Seller", "Items Summary", "Total (Rs)", "Cash Paid (Rs)", "UPI Paid (Rs)", "Total Paid (Rs)",
        "Balance (Rs)", "Payment Status", "Order Status", "Cancel Reason"
    ])

    for o in orders:
        items_summary = "; ".join([f"{it.item_name} {it.size} x{it.quantity}" for it in o.items])
        cash_val = sum(p.amount for p in o.payments if p.method.lower() == "cash")
        upi_val = sum(p.amount for p in o.payments if p.method.lower() == "upi")
        writer.writerow([
            o.bill_no,
            o.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            o.nagar.name if o.nagar else "",
            o.buyer.name if o.buyer else "",
            o.buyer.phone if o.buyer else "",
            o.seller.name if o.seller else "",
            items_summary,
            o.total,
            cash_val,
            upi_val,
            o.paid_amount,
            o.balance,
            o.payment_status,
            o.order_status,
            o.cancel_reason or ""
        ])

    csv_data = output.getvalue()
    filename = f"sanghmart_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# ---------------- 7. AUDIT LOG REPORT ----------------
@router.get("/audit-log")
async def get_audit_log(
    limit: int = 100,
    admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(AuditLog).options(selectinload(AuditLog.user)).order_by(AuditLog.id.desc()).limit(limit)
    res = await db.execute(stmt)
    logs = res.scalars().all()
    return [
        {
            "id": l.id,
            "action": l.action,
            "entity": l.entity,
            "entity_id": l.entity_id,
            "user_id": l.user_id,
            "user_name": l.user.name if l.user else "System",
            "before": l.before,
            "after": l.after,
            "reason": l.reason,
            "created_at": l.created_at.isoformat()
        }
        for l in logs
    ]
