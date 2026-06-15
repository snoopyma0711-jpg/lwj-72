from typing import Dict, List
from app.models import (
    Store, Product, InventoryItem, ReplenishmentRequest,
    Wave, RearrangementRecord, WaveStatus, RequestStatus
)


class Database:
    def __init__(self):
        self.stores: Dict[str, Store] = {}
        self.products: Dict[str, Product] = {}
        self.inventory: Dict[str, InventoryItem] = {}
        self.requests: Dict[str, ReplenishmentRequest] = {}
        self.waves: Dict[str, Wave] = {}
        self.rearrangement_records: List[RearrangementRecord] = []
        self.wave_counter: int = 0
        self.request_counter: int = 0

    def add_store(self, store: Store):
        self.stores[store.store_id] = store

    def add_product(self, product: Product):
        self.products[product.product_id] = product

    def set_inventory(self, item: InventoryItem):
        self.inventory[item.product_id] = item

    def add_request(self, request: ReplenishmentRequest):
        self.requests[request.request_id] = request

    def add_wave(self, wave: Wave):
        self.waves[wave.wave_id] = wave

    def add_rearrangement_record(self, record: RearrangementRecord):
        self.rearrangement_records.append(record)

    def next_wave_id(self) -> str:
        self.wave_counter += 1
        return f"WAVE-{self.wave_counter:03d}"

    def next_request_id(self) -> str:
        self.request_counter += 1
        return f"REQ-{self.request_counter:04d}"

    def get_pending_requests(self) -> List[ReplenishmentRequest]:
        return [r for r in self.requests.values() if r.status == RequestStatus.PENDING]

    def get_active_waves(self) -> List[Wave]:
        return [w for w in self.waves.values()
                if w.status in (WaveStatus.DRAFT, WaveStatus.PENDING_CONFIRM)]

    def get_confirmed_waves(self) -> List[Wave]:
        return [w for w in self.waves.values() if w.status == WaveStatus.CONFIRMED]


db = Database()
