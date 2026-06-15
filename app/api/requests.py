from fastapi import APIRouter, HTTPException
from typing import List, Dict, Optional
from pydantic import BaseModel

from app.database import db
from app.models import ReplenishmentRequest, RequestStatus, RearrangementRecord
from app.services import wave_service

router = APIRouter(prefix="/requests", tags=["补货需求"])


class CreateRequestRequest(BaseModel):
    store_id: str
    items: Dict[str, int]


class UpdateRequestRequest(BaseModel):
    items: Dict[str, int]


@router.get("", response_model=List[Dict])
def list_requests(status: Optional[str] = None, store_id: Optional[str] = None):
    result = []
    for req in db.requests.values():
        if status and req.status != status:
            continue
        if store_id and req.store_id != store_id:
            continue
        store = db.stores.get(req.store_id)
        item_details = []
        for pid, qty in req.items.items():
            product = db.products.get(pid)
            allocated_qty = req.allocated_items.get(pid, 0)
            item_details.append({
                "product_id": pid,
                "product_name": product.product_name if product else "",
                "requested_quantity": qty,
                "allocated_quantity": allocated_qty,
                "unit": product.unit if product else "件"
            })
        result.append({
            "request_id": req.request_id,
            "store_id": req.store_id,
            "store_name": store.store_name if store else "",
            "store_priority": store.priority if store else 0,
            "items": item_details,
            "status": req.status,
            "wave_id": req.wave_id,
            "created_at": req.created_at,
            "updated_at": req.updated_at
        })
    return result


@router.get("/{request_id}", response_model=Dict)
def get_request(request_id: str):
    req = db.requests.get(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="需求不存在")
    store = db.stores.get(req.store_id)
    item_details = []
    for pid, qty in req.items.items():
        product = db.products.get(pid)
        allocated_qty = req.allocated_items.get(pid, 0)
        item_details.append({
            "product_id": pid,
            "product_name": product.product_name if product else "",
            "requested_quantity": qty,
            "allocated_quantity": allocated_qty,
            "unit": product.unit if product else "件"
        })
    return {
        "request_id": req.request_id,
        "store_id": req.store_id,
        "store_name": store.store_name if store else "",
        "store_priority": store.priority if store else 0,
        "items": item_details,
        "status": req.status,
        "wave_id": req.wave_id,
        "created_at": req.created_at,
        "updated_at": req.updated_at
    }


@router.post("", response_model=Dict)
def create_request(req_data: CreateRequestRequest):
    if req_data.store_id not in db.stores:
        raise HTTPException(status_code=400, detail="门店不存在")
    for pid in req_data.items:
        if pid not in db.products:
            raise HTTPException(status_code=400, detail=f"商品 {pid} 不存在")

    request = wave_service.add_request(req_data.store_id, req_data.items)

    store = db.stores.get(request.store_id)
    return {
        "request_id": request.request_id,
        "store_id": request.store_id,
        "store_name": store.store_name if store else "",
        "items": request.items,
        "status": request.status,
        "created_at": request.created_at
    }


@router.put("/{request_id}/quantity", response_model=RearrangementRecord)
def update_request_quantity(request_id: str, req_data: UpdateRequestRequest):
    if request_id not in db.requests:
        raise HTTPException(status_code=404, detail="需求不存在")

    req = db.requests.get(request_id)
    if req.status == RequestStatus.CONFIRMED:
        raise HTTPException(status_code=400, detail="已确认的需求不能修改")

    record = wave_service.update_request_quantity(request_id, req_data.items)
    if not record:
        raise HTTPException(status_code=400, detail="修改失败")

    return record
