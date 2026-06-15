from fastapi import APIRouter
from typing import List, Dict

from app.database import db
from app.models import InventoryItem
from app.services import wave_service

router = APIRouter(prefix="/inventory", tags=["库存"])


@router.get("", response_model=List[Dict])
def list_inventory():
    result = []
    for product_id, inv in db.inventory.items():
        product = db.products.get(product_id)
        result.append({
            "product_id": product_id,
            "product_name": product.product_name if product else "",
            "total_quantity": inv.total_quantity,
            "allocated_quantity": inv.allocated_quantity,
            "locked_quantity": inv.locked_quantity,
            "available_quantity": inv.available_quantity,
            "unit": product.unit if product else "件"
        })
    return result


@router.get("/summary", response_model=Dict)
def get_inventory_summary():
    return {
        "available": wave_service.get_available_inventory(),
        "locked": wave_service.get_locked_inventory(),
        "allocated": wave_service.get_allocated_inventory()
    }
