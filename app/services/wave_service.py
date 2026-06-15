from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
from copy import deepcopy
import uuid

from app.database import db
from app.models import (
    Wave, ReplenishmentRequest, InventoryItem,
    WaveStatus, RequestStatus,
    RearrangementRecord, StoreChange, ChangeType
)


WAVE_CONFIRM_TIMEOUT_MINUTES = 10


def get_available_inventory() -> Dict[str, int]:
    available = {}
    for product_id, inv in db.inventory.items():
        available[product_id] = inv.available_quantity
    return available


def get_allocated_inventory() -> Dict[str, int]:
    allocated = {}
    for product_id, inv in db.inventory.items():
        allocated[product_id] = inv.allocated_quantity
    return allocated


def get_locked_inventory() -> Dict[str, int]:
    locked = {}
    for product_id, inv in db.inventory.items():
        locked[product_id] = inv.locked_quantity
    return locked


def can_fulfill_request(request: ReplenishmentRequest, available: Dict[str, int]) -> bool:
    for product_id, qty in request.items.items():
        if product_id not in available:
            return False
        if available[product_id] < qty:
            return False
    return True


def lock_inventory_for_request(request: ReplenishmentRequest):
    for product_id, qty in request.items.items():
        if product_id in db.inventory:
            db.inventory[product_id].locked_quantity += qty


def unlock_inventory_for_request(request: ReplenishmentRequest):
    for product_id, qty in request.items.items():
        if product_id in db.inventory:
            db.inventory[product_id].locked_quantity = max(
                0, db.inventory[product_id].locked_quantity - qty
            )


def allocate_inventory_for_request(request: ReplenishmentRequest):
    for product_id, qty in request.items.items():
        if product_id in db.inventory:
            db.inventory[product_id].allocated_quantity += qty
            db.inventory[product_id].locked_quantity = max(
                0, db.inventory[product_id].locked_quantity - qty
            )


def deallocate_inventory_for_request(request: ReplenishmentRequest):
    for product_id, qty in request.items.items():
        if product_id in db.inventory:
            db.inventory[product_id].allocated_quantity = max(
                0, db.inventory[product_id].allocated_quantity - qty
            )


def sort_requests_by_priority(requests: List[ReplenishmentRequest]) -> List[ReplenishmentRequest]:
    def sort_key(r: ReplenishmentRequest):
        store = db.stores.get(r.store_id)
        priority = store.priority if store else 10
        return (priority, r.created_at)

    return sorted(requests, key=sort_key)


def record_rearrangement(
    trigger: str,
    before_waves: List[Wave],
    after_waves: List[Wave],
    store_changes: List[StoreChange],
    reason_summary: str
):
    record = RearrangementRecord(
        rearrangement_id=str(uuid.uuid4())[:8],
        timestamp=datetime.now(),
        trigger=trigger,
        before_waves=deepcopy(before_waves),
        after_waves=deepcopy(after_waves),
        store_changes=store_changes,
        reason_summary=reason_summary
    )
    db.add_rearrangement_record(record)
    return record


def compute_store_changes(
    before_waves: List[Wave],
    after_waves: List[Wave]
) -> List[StoreChange]:
    changes = []

    before_store_wave = {}
    for wave in before_waves:
        if wave.status == WaveStatus.CONFIRMED:
            continue
        for store_id in wave.store_ids:
            before_store_wave[store_id] = wave.wave_id

    after_store_wave = {}
    for wave in after_waves:
        if wave.status == WaveStatus.CONFIRMED:
            continue
        for store_id in wave.store_ids:
            after_store_wave[store_id] = wave.wave_id

    all_stores = set(before_store_wave.keys()) | set(after_store_wave.keys())

    for store_id in sorted(all_stores):
        before_wave_id = before_store_wave.get(store_id)
        after_wave_id = after_store_wave.get(store_id)

        if before_wave_id is None and after_wave_id is not None:
            changes.append(StoreChange(
                store_id=store_id,
                change_type=ChangeType.ADDED,
                from_wave=None,
                to_wave=after_wave_id,
                reason=f"门店 {store_id} 新增进入波次 {after_wave_id}"
            ))
        elif before_wave_id is not None and after_wave_id is None:
            changes.append(StoreChange(
                store_id=store_id,
                change_type=ChangeType.REMOVED,
                from_wave=before_wave_id,
                to_wave=None,
                reason=f"门店 {store_id} 从波次 {before_wave_id} 移出，库存不足"
            ))
        elif before_wave_id != after_wave_id:
            changes.append(StoreChange(
                store_id=store_id,
                change_type=ChangeType.MOVED_IN,
                from_wave=before_wave_id,
                to_wave=after_wave_id,
                reason=f"门店 {store_id} 从波次 {before_wave_id} 调整到波次 {after_wave_id}"
            ))

    return changes


def check_expired_waves() -> List[str]:
    now = datetime.now()
    expired_wave_ids = []

    for wave in list(db.waves.values()):
        if wave.status == WaveStatus.PENDING_CONFIRM and wave.expires_at and wave.expires_at <= now:
            expired_wave_ids.append(wave.wave_id)
            wave.status = WaveStatus.EXPIRED

            for request_id in wave.request_ids:
                if request_id in db.requests:
                    req = db.requests[request_id]
                    unlock_inventory_for_request(req)
                    req.status = RequestStatus.PENDING
                    req.wave_id = None
                    req.allocated_items = {}
                    req.updated_at = now

    return expired_wave_ids


def _dissolve_wave(wave_id: str):
    if wave_id not in db.waves:
        return

    wave = db.waves[wave_id]
    for request_id in wave.request_ids:
        if request_id in db.requests:
            req = db.requests[request_id]
            if wave.status in (WaveStatus.DRAFT, WaveStatus.PENDING_CONFIRM):
                unlock_inventory_for_request(req)
            req.status = RequestStatus.PENDING
            req.wave_id = None
            req.allocated_items = {}
            req.updated_at = datetime.now()

    del db.waves[wave_id]


def _build_new_draft_waves(pending_requests: List[ReplenishmentRequest]) -> List[Wave]:
    sorted_requests = sort_requests_by_priority(pending_requests)
    new_waves: List[Wave] = []
    current_wave = None
    current_wave_items: Dict[str, int] = {}

    for request in sorted_requests:
        available = get_available_inventory()

        if can_fulfill_request(request, available):
            if current_wave is None:
                wave_id = db.next_wave_id()
                current_wave = Wave(
                    wave_id=wave_id,
                    wave_number=int(wave_id.split("-")[1]),
                    status=WaveStatus.DRAFT,
                    store_ids=[],
                    request_ids=[],
                    items={}
                )
                new_waves.append(current_wave)
                current_wave_items = {}

            current_wave.store_ids.append(request.store_id)
            current_wave.request_ids.append(request.request_id)
            for pid, qty in request.items.items():
                current_wave_items[pid] = current_wave_items.get(pid, 0) + qty
            current_wave.items = dict(current_wave_items)

            lock_inventory_for_request(request)
            request.status = RequestStatus.IN_WAVE
            request.wave_id = current_wave.wave_id
            request.allocated_items = dict(request.items)
            request.updated_at = datetime.now()

    return new_waves


def rebuild_draft_waves() -> Tuple[List[Wave], List[Wave], str]:
    before_waves = deepcopy(list(db.waves.values()))

    for wave in list(db.waves.values()):
        if wave.status == WaveStatus.DRAFT:
            _dissolve_wave(wave.wave_id)

    pending_requests = db.get_pending_requests()
    new_waves = _build_new_draft_waves(pending_requests)

    for wave in new_waves:
        db.add_wave(wave)

    after_waves = list(db.waves.values())

    reason_parts = []
    if new_waves:
        reason_parts.append(f"生成了 {len(new_waves)} 个新草稿波次")
    pending_count = len(db.get_pending_requests())
    if pending_count > 0:
        reason_parts.append(f"{pending_count} 个需求因库存不足继续等待")

    reason_summary = "；".join(reason_parts) if reason_parts else "无变化"

    return before_waves, after_waves, reason_summary


def rebuild_waves_with_release(release_wave_ids: List[str] = None) -> Tuple[List[Wave], List[Wave], str]:
    before_waves = deepcopy(list(db.waves.values()))

    if release_wave_ids:
        for wid in release_wave_ids:
            _dissolve_wave(wid)

    for wave in list(db.waves.values()):
        if wave.status == WaveStatus.DRAFT:
            _dissolve_wave(wave.wave_id)

    pending_requests = db.get_pending_requests()
    new_waves = _build_new_draft_waves(pending_requests)

    for wave in new_waves:
        db.add_wave(wave)

    after_waves = list(db.waves.values())

    reason_parts = []
    if release_wave_ids:
        reason_parts.append(f"释放了 {len(release_wave_ids)} 个波次的库存")
    if new_waves:
        reason_parts.append(f"生成了 {len(new_waves)} 个新草稿波次")
    pending_count = len(db.get_pending_requests())
    if pending_count > 0:
        reason_parts.append(f"{pending_count} 个需求等待分配")

    reason_summary = "；".join(reason_parts) if reason_parts else "无变化"

    return before_waves, after_waves, reason_summary


def generate_waves(trigger: str = "manual") -> RearrangementRecord:
    check_expired_waves()

    before_waves, after_waves, reason_summary = rebuild_draft_waves()

    store_changes = compute_store_changes(before_waves, after_waves)

    record = record_rearrangement(
        trigger=trigger,
        before_waves=before_waves,
        after_waves=after_waves,
        store_changes=store_changes,
        reason_summary=reason_summary
    )

    return record


def confirm_wave(wave_id: str) -> Optional[Wave]:
    if wave_id not in db.waves:
        return None

    wave = db.waves[wave_id]
    if wave.status not in (WaveStatus.DRAFT, WaveStatus.PENDING_CONFIRM):
        return None

    now = datetime.now()
    wave.status = WaveStatus.CONFIRMED
    wave.confirmed_at = now

    for request_id in wave.request_ids:
        if request_id in db.requests:
            req = db.requests[request_id]
            allocate_inventory_for_request(req)
            req.status = RequestStatus.CONFIRMED
            req.updated_at = now

    return wave


def submit_wave_for_confirmation(wave_id: str, timeout_minutes: int = WAVE_CONFIRM_TIMEOUT_MINUTES) -> Optional[Wave]:
    if wave_id not in db.waves:
        return None

    wave = db.waves[wave_id]
    if wave.status != WaveStatus.DRAFT:
        return None

    wave.status = WaveStatus.PENDING_CONFIRM
    wave.expires_at = datetime.now() + timedelta(minutes=timeout_minutes)

    return wave


def update_request_quantity(request_id: str, new_items: Dict[str, int]) -> Optional[RearrangementRecord]:
    if request_id not in db.requests:
        return None

    request = db.requests[request_id]

    if request.status == RequestStatus.CONFIRMED:
        return None

    affected_wave_id = None
    if request.status == RequestStatus.IN_WAVE and request.wave_id:
        wave_id = request.wave_id
        if wave_id in db.waves:
            wave = db.waves[wave_id]
            if wave.status == WaveStatus.CONFIRMED:
                return None
            affected_wave_id = wave_id

    request.items = dict(new_items)
    request.updated_at = datetime.now()

    release_wave_ids = [affected_wave_id] if affected_wave_id else None

    before_waves, after_waves, reason_summary = rebuild_waves_with_release(release_wave_ids)

    store_changes = compute_store_changes(before_waves, after_waves)

    record = record_rearrangement(
        trigger=f"update_request:{request_id}",
        before_waves=before_waves,
        after_waves=after_waves,
        store_changes=store_changes,
        reason_summary=f"修改需求 {request_id} 后重排 - {reason_summary}"
    )

    return record


def add_request(store_id: str, items: Dict[str, int]) -> ReplenishmentRequest:
    request_id = db.next_request_id()
    request = ReplenishmentRequest(
        request_id=request_id,
        store_id=store_id,
        items=items,
        status=RequestStatus.PENDING
    )
    db.add_request(request)
    return request


def force_release_expired_waves() -> List[str]:
    expired_ids = check_expired_waves()
    if expired_ids:
        before_waves, after_waves, reason_summary = rebuild_waves_with_release(expired_ids)
        store_changes = compute_store_changes(before_waves, after_waves)
        record_rearrangement(
            trigger="expire_check",
            before_waves=before_waves,
            after_waves=after_waves,
            store_changes=store_changes,
            reason_summary=f"超时释放后重排 - {reason_summary}"
        )
    return expired_ids
