from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.data.demo_data import init_demo_data
from app.api.stores import router as stores_router
from app.api.products import router as products_router
from app.api.inventory import router as inventory_router
from app.api.requests import router as requests_router
from app.api.waves import router as waves_router
from app.api.rearrangements import router as rearrangements_router

app = FastAPI(
    title="拣货波次编排服务",
    description="连锁咖啡门店夜间补货波次编排系统 - 支持整单原则、库存锁定、超时释放、重排追踪",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    init_demo_data()


@app.get("/", tags=["系统"])
async def root():
    return {
        "service": "拣货波次编排服务",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "demo": "/demo"
    }


@app.get("/status", tags=["系统"])
async def get_status():
    from app.database import db
    return {
        "stores": len(db.stores),
        "products": len(db.products),
        "inventory_items": len(db.inventory),
        "requests": len(db.requests),
        "waves": len(db.waves),
        "rearrangement_records": len(db.rearrangement_records)
    }


@app.get("/demo", tags=["系统"])
async def demo_overview():
    from app.database import db
    from app.services import wave_service

    stores = []
    for sid, store in db.stores.items():
        stores.append({
            "store_id": sid,
            "store_name": store.store_name,
            "priority": store.priority
        })

    inventory = []
    for pid, inv in db.inventory.items():
        product = db.products.get(pid)
        inventory.append({
            "product_id": pid,
            "product_name": product.product_name if product else "",
            "total": inv.total_quantity,
            "allocated": inv.allocated_quantity,
            "locked": inv.locked_quantity,
            "available": inv.available_quantity,
            "unit": product.unit if product else "件"
        })

    requests = []
    for rid, req in db.requests.items():
        store = db.stores.get(req.store_id)
        requests.append({
            "request_id": rid,
            "store_id": req.store_id,
            "store_name": store.store_name if store else "",
            "priority": store.priority if store else 0,
            "item_count": len(req.items),
            "status": req.status,
            "wave_id": req.wave_id
        })

    return {
        "stores": stores,
        "inventory": inventory,
        "requests": requests,
        "wave_count": len(db.waves),
        "rearrangement_count": len(db.rearrangement_records)
    }


app.include_router(stores_router)
app.include_router(products_router)
app.include_router(inventory_router)
app.include_router(requests_router)
app.include_router(waves_router)
app.include_router(rearrangements_router)
