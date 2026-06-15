from fastapi import APIRouter
from typing import List, Dict

from app.database import db
from app.models import RearrangementRecord

router = APIRouter(prefix="/rearrangements", tags=["重排历史"])


@router.get("", response_model=List[Dict])
def list_rearrangements(limit: int = 20):
    records = db.rearrangement_records[-limit:]
    result = []
    for record in reversed(records):
        result.append({
            "rearrangement_id": record.rearrangement_id,
            "timestamp": record.timestamp,
            "trigger": record.trigger,
            "reason_summary": record.reason_summary,
            "store_change_count": len(record.store_changes),
            "store_changes": [
                {
                    "store_id": sc.store_id,
                    "change_type": sc.change_type,
                    "from_wave": sc.from_wave,
                    "to_wave": sc.to_wave,
                    "reason": sc.reason
                }
                for sc in record.store_changes
            ],
            "before_wave_count": len(record.before_waves),
            "after_wave_count": len(record.after_waves)
        })
    return result


@router.get("/{rearrangement_id}", response_model=Dict)
def get_rearrangement(rearrangement_id: str):
    record = None
    for r in db.rearrangement_records:
        if r.rearrangement_id == rearrangement_id:
            record = r
            break

    if not record:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="重排记录不存在")

    def wave_to_dict(wave):
        return {
            "wave_id": wave.wave_id,
            "wave_number": wave.wave_number,
            "status": wave.status,
            "store_ids": wave.store_ids,
            "items": wave.items
        }

    return {
        "rearrangement_id": record.rearrangement_id,
        "timestamp": record.timestamp,
        "trigger": record.trigger,
        "reason_summary": record.reason_summary,
        "store_changes": [
            {
                "store_id": sc.store_id,
                "change_type": sc.change_type,
                "from_wave": sc.from_wave,
                "to_wave": sc.to_wave,
                "reason": sc.reason
            }
            for sc in record.store_changes
        ],
        "before_waves": [wave_to_dict(w) for w in record.before_waves],
        "after_waves": [wave_to_dict(w) for w in record.after_waves]
    }


@router.get("/compare/{rearrangement_id}")
def compare_rearrangement(rearrangement_id: str):
    record = None
    for r in db.rearrangement_records:
        if r.rearrangement_id == rearrangement_id:
            record = r
            break

    if not record:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="重排记录不存在")

    before_stores = {}
    for wave in record.before_waves:
        if wave.status == "confirmed":
            continue
        for sid in wave.store_ids:
            before_stores[sid] = wave.wave_id

    after_stores = {}
    for wave in record.after_waves:
        if wave.status == "confirmed":
            continue
        for sid in wave.store_ids:
            after_stores[sid] = wave.wave_id

    all_stores = set(before_stores.keys()) | set(after_stores.keys())

    comparisons = []
    for sid in sorted(all_stores):
        store = db.stores.get(sid)
        before_wave = before_stores.get(sid, "-")
        after_wave = after_stores.get(sid, "-")

        if before_wave == after_wave:
            status = "unchanged"
        elif before_wave == "-":
            status = "added"
        elif after_wave == "-":
            status = "removed"
        else:
            status = "moved"

        comparisons.append({
            "store_id": sid,
            "store_name": store.store_name if store else "",
            "before_wave": before_wave,
            "after_wave": after_wave,
            "status": status
        })

    return {
        "rearrangement_id": record.rearrangement_id,
        "timestamp": record.timestamp,
        "trigger": record.trigger,
        "reason_summary": record.reason_summary,
        "comparisons": comparisons
    }
