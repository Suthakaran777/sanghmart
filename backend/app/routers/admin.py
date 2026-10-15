from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin, get_password_hash
from app.repositories.base import Repository
from app.schemas.schemas import (
    UserCreate, UserResponse,
    NagarCreate, NagarResponse,
    ItemCreate, ItemResponse,
    StockUpdateRequest, StockMovementResponse
)

router = APIRouter(prefix="/admin", tags=["admin"])

# ---------------- SELLERS ----------------
@router.get("/sellers", response_model=List[UserResponse])
async def list_sellers(admin = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    repo = Repository(db)
    sellers_with_sales = await repo.list_sellers()
    res = []
    for user, total_sales in sellers_with_sales:
        resp = UserResponse(
            id=user.id,
            name=user.name,
            phone=user.phone,
            username=user.username,
            role=user.role,
            is_active=user.is_active,
            total_sales=total_sales
        )
        res.append(resp)
    return res

@router.post("/sellers", response_model=UserResponse)
async def create_seller(req: UserCreate, admin = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    repo = Repository(db)
    existing = await repo.get_user_by_username(req.username.strip())
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    hashed = get_password_hash(req.password)
    user = await repo.create_user(
        name=req.name,
        username=req.username.strip(),
        password_hash=hashed,
        role="seller",
        phone=req.phone
    )
    await repo.add_audit("CREATE_SELLER", "User", str(user.id), after=user.username, user_id=admin.id)
    await db.commit()
    return user

@router.put("/sellers/{seller_id}/toggle-active")
async def toggle_seller(seller_id: int, admin = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    repo = Repository(db)
    user = await repo.get_user_by_id(seller_id)
    if not user or user.role != "seller":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Seller not found")
    new_state = not user.is_active
    await repo.update_user_status(seller_id, new_state)
    await repo.add_audit("TOGGLE_SELLER", "User", str(seller_id), before=str(not new_state), after=str(new_state), user_id=admin.id)
    await db.commit()
    return {"id": seller_id, "is_active": new_state}

@router.put("/sellers/{seller_id}/reset-password")
async def reset_password(seller_id: int, new_password: str, admin = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    repo = Repository(db)
    user = await repo.get_user_by_id(seller_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Seller not found")
    hashed = get_password_hash(new_password)
    await repo.update_user_password(seller_id, hashed)
    await repo.add_audit("RESET_PASSWORD", "User", str(seller_id), user_id=admin.id)
    await db.commit()
    return {"message": "Password reset successfully"}

# ---------------- NAGARS ----------------
@router.get("/nagars", response_model=List[NagarResponse])
async def list_nagars(admin = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    repo = Repository(db)
    return await repo.list_nagars(active_only=False)

@router.post("/nagars", response_model=NagarResponse)
async def create_nagar(req: NagarCreate, admin = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    repo = Repository(db)
    nagar = await repo.create_nagar(req.name)
    await repo.add_audit("CREATE_NAGAR", "Nagar", str(nagar.id), after=nagar.name, user_id=admin.id)
    await db.commit()
    return nagar

# ---------------- ITEMS & SIZES ----------------
@router.get("/items", response_model=List[ItemResponse])
async def list_items(admin = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    repo = Repository(db)
    return await repo.list_items(active_only=False)

@router.post("/items", response_model=ItemResponse)
async def create_item(req: ItemCreate, admin = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    repo = Repository(db)
    existing = await repo.get_item_by_name(req.name)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Item already exists")
    item = await repo.create_item(req.name, req.price, req.sizes)
    await repo.add_audit("CREATE_ITEM", "Item", str(item.id), after=item.name, user_id=admin.id)
    await db.commit()
    # refresh to load sizes
    return await repo.get_item_by_id(item.id)

# ---------------- STOCK MANAGEMENT ----------------
@router.put("/stock")
async def update_stock(req: StockUpdateRequest, admin = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    repo = Repository(db)
    try:
        updated_item_size = await repo.update_stock(
            item_size_id=req.item_size_id,
            qty_delta=req.qty_delta,
            movement_type="adjustment",
            reason=req.reason,
            user_id=admin.id
        )
        await repo.add_audit("STOCK_UPDATE", "ItemSize", str(req.item_size_id), after=f"delta:{req.qty_delta}", reason=req.reason, user_id=admin.id)
        await db.commit()
        return {
            "item_size_id": updated_item_size.id,
            "new_stock": updated_item_size.stock_qty,
            "message": "Stock updated successfully"
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/stock/history", response_model=List[StockMovementResponse])
async def get_stock_history(admin = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    repo = Repository(db)
    return await repo.list_stock_movements(limit=200)

# ---------------- SETTINGS ----------------
@router.get("/settings")
async def get_settings(admin = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    repo = Repository(db)
    upi_id = await repo.get_setting("upi_id", "sanghmart@upi")
    bill_header = await repo.get_setting("bill_header", "Sangh Mart")
    return {"upi_id": upi_id, "bill_header": bill_header}

@router.put("/settings")
async def update_settings(settings_dict: dict, admin = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    repo = Repository(db)
    for k, v in settings_dict.items():
        await repo.set_setting(k, str(v))
    await repo.add_audit("UPDATE_SETTINGS", "Setting", "all", user_id=admin.id)
    await db.commit()
    return {"message": "Settings updated"}
