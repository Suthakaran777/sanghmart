from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, Base, AsyncSessionLocal
from app.core.security import get_password_hash
from app.repositories.base import Repository
from app.routers import auth, admin, orders, payments, admin_dashboard

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    # Seed default admin and sample data if not present
    async with AsyncSessionLocal() as session:
        repo = Repository(session)
        admin_user = await repo.get_user_by_username("adminji")
        if not admin_user:
            admin_user = await repo.create_user(
                name="Head Organizer",
                username="adminji",
                password_hash=get_password_hash("admin123"),
                role="admin",
                phone="+919999999999"
            )
            # Seed standard uniform items with updated official prices and sizes
            pant_sizes = [str(x) for x in range(22, 50, 2)]  # 22, 24, 26..48
            shirt_sizes = [str(x) for x in range(30, 50, 2)]  # 30, 32, 34..48
            shoe_sizes = [str(x) for x in range(5, 15)]  # 5 to 14
            universal_size = ["Universal"]

            uniform_items = [
                ("Pant", 350, pant_sizes),
                ("Shirt", 220, shirt_sizes),
                ("Socks", 30, universal_size),
                ("Cap", 30, universal_size),
                ("Belt", 85, universal_size),
                ("Shoe", 170, shoe_sizes)
            ]
            for item_name, price, sizes in uniform_items:
                created_item = await repo.create_item(item_name, price, sizes)
                item_loaded = await repo.get_item_by_id(created_item.id)
                # Seed initial stock of 50 for each size
                for s in item_loaded.sizes:
                    await repo.update_stock(
                        item_size_id=s.id,
                        qty_delta=50,
                        movement_type="opening",
                        reason="Initial stock provisioning",
                        user_id=admin_user.id
                    )

            # Seed Nagars from official list
            nagars = [
                "MARUTHAMALAI NAGAR",
                "TELUNGUPALAYAM NAGAR",
                "KEMPATTI COLONY",
                "RAJA VEETHI NAGAR",
                "RAMANATHAPURAM NAGAR",
                "SOWRIPALAYAM",
                "SINGANALLUR NAGAR",
                "VELLALUR NAGAR",
                "POTHANUR NAGAR",
                "SUNDRAPURAM NAGAR",
                "KUNIYAMUTHUR NAGAR",
                "KOVAIPUDHUR NAGAR",
                "THUDIYALOOR NAGAR",
                "VELANDI PALAYAM",
                "KAVUDAMPALAYAM",
                "SAIBABA NAGAR",
                "RAM NAGAR",
                "R.S.PURAM NAGAR",
                "PN PALAYAM NAGAR",
                "GANAPATHI NAGAR",
                "SARAVANAMPATTI NAGAR",
                "PEELAMEDU NAGAR",
                "KALAPATTI NAGAR"
            ]
            for n in nagars:
                await repo.create_nagar(n)
                
            # Seed default settings
            await repo.set_setting("bill_header", "Sangh Mart")
            await repo.set_setting("upi_id", "asuthakaran2006@oksbi")
            
            # Seed all 12 official sellers
            official_sellers = [
                "suthakaran",
                "harivatcha",
                "vishal",
                "sreevaishnav",
                "anish",
                "kirankumar",
                "yogiram",
                "munees",
                "dinesh",
                "ashwin",
                "jothi",
                "sathriyan"
            ]
            for idx, uname in enumerate(official_sellers, 1):
                await repo.create_user(
                    name=uname.capitalize(),
                    username=uname.lower(),
                    password_hash=get_password_hash("seller123"),
                    role="seller",
                    phone=f"+9198765432{idx:02d}"
                )
            
            await session.commit()
            
    yield

app = FastAPI(
    title=settings.APP_NAME,
    description="Vijayadashami Uniform Sales Management System API",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(orders.router)
app.include_router(payments.router)
app.include_router(admin_dashboard.router)

@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME}
