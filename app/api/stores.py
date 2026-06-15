from fastapi import APIRouter
from typing import List, Dict

from app.database import db
from app.models import Store

router = APIRouter(prefix="/stores", tags=["门店"])


@router.get("", response_model=List[Store])
def list_stores():
    return list(db.stores.values())


@router.get("/{store_id}", response_model=Store)
def get_store(store_id: str):
    return db.stores.get(store_id)
