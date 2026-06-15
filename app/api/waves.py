from fastapi import APIRouter, HTTPException
from typing import List, Dict, Optional
from pydantic import BaseModel

from app.database import db
from app.models import Wave, WaveStatus, RearrangementRecord
from app.services import wave_service

router = APIRouter(prefix="/waves", tags=["波次"])


class GenerateWavesRequest(BaseModel):
    trigger: str = "manual"


class ConfirmWaveRequest(BaseModel):
    pass


class SubmitConfirmRequest(BaseModel):
    timeout_minutes: int = 10


@router.get("", response_model=List[Dict])
def list_waves(status: Optional[str] = None):
    result = []
    for wave in sorted(db.waves.values(), key=lambda w: w.wave_number):
        if status and wave.status != status:
            continue

        store_details = []
        for store_id in wave.store_ids:
            store = db.stores.get(store_id)
            store_details.append({
                "store_id": store_id,
                "store_name": store.store_name if store else "",
                "priority": store.priority if store else 0
            })

        item_details = []
        for pid, qty in wave.items.items():
            product = db.products.get(pid)
            item_details.append({
                "product_id": pid,
                "product_name": product.product_name if product else "",
                "quantity": qty,
                "unit": product.unit if product else "件"
            })

        result.append({
            "wave_id": wave.wave_id,
            "wave_number": wave.wave_number,
            "status": wave.status,
            "stores": store_details,
            "request_count": len(wave.request_ids),
            "items": item_details,
            "expires_at": wave.expires_at,
            "created_at": wave.created_at,
            "confirmed_at": wave.confirmed_at
        })
    return result


@router.get("/{wave_id}", response_model=Dict)
def get_wave(wave_id: str):
    wave = db.waves.get(wave_id)
    if not wave:
        raise HTTPException(status_code=404, detail="波次不存在")

    store_details = []
    for store_id in wave.store_ids:
        store = db.stores.get(store_id)
        store_details.append({
            "store_id": store_id,
            "store_name": store.store_name if store else "",
            "priority": store.priority if store else 0
        })

    request_details = []
    for req_id in wave.request_ids:
        req = db.requests.get(req_id)
        if req:
            request_details.append({
                "request_id": req.request_id,
                "store_id": req.store_id,
                "items": req.items
            })

    item_details = []
    for pid, qty in wave.items.items():
        product = db.products.get(pid)
        item_details.append({
            "product_id": pid,
            "product_name": product.product_name if product else "",
            "quantity": qty,
            "unit": product.unit if product else "件"
        })

    return {
        "wave_id": wave.wave_id,
        "wave_number": wave.wave_number,
        "status": wave.status,
        "stores": store_details,
        "requests": request_details,
        "items": item_details,
        "expires_at": wave.expires_at,
        "created_at": wave.created_at,
        "confirmed_at": wave.confirmed_at
    }


@router.post("/generate", response_model=RearrangementRecord)
def generate_waves(req: GenerateWavesRequest):
    record = wave_service.generate_waves(trigger=req.trigger)
    return record


@router.post("/{wave_id}/submit-confirm", response_model=Wave)
def submit_wave_for_confirmation(wave_id: str, req: SubmitConfirmRequest):
    wave = wave_service.submit_wave_for_confirmation(wave_id, req.timeout_minutes)
    if not wave:
        raise HTTPException(status_code=400, detail="提交失败，波次不存在或状态不正确")
    return wave


@router.post("/{wave_id}/confirm", response_model=Wave)
def confirm_wave(wave_id: str):
    wave = wave_service.confirm_wave(wave_id)
    if not wave:
        raise HTTPException(status_code=400, detail="确认失败，波次不存在或状态不正确")
    return wave


@router.post("/check-expired", response_model=Dict)
def check_expired_waves():
    expired_ids = wave_service.force_release_expired_waves()
    return {
        "expired_count": len(expired_ids),
        "expired_wave_ids": expired_ids
    }
