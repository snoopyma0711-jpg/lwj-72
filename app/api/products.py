from fastapi import APIRouter
from typing import List

from app.database import db
from app.models import Product

router = APIRouter(prefix="/products", tags=["商品"])


@router.get("", response_model=List[Product])
def list_products():
    return list(db.products.values())


@router.get("/{product_id}", response_model=Product)
def get_product(product_id: str):
    return db.products.get(product_id)
