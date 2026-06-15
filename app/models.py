from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class Store(BaseModel):
    store_id: str
    store_name: str
    priority: int = Field(default=5, description="优先级，1最高，10最低")


class Product(BaseModel):
    product_id: str
    product_name: str
    unit: str = "件"


class InventoryItem(BaseModel):
    product_id: str
    total_quantity: int
    allocated_quantity: int = 0
    locked_quantity: int = 0

    @property
    def available_quantity(self) -> int:
        return self.total_quantity - self.allocated_quantity - self.locked_quantity


class RequestStatus(str, Enum):
    PENDING = "pending"
    IN_WAVE = "in_wave"
    CONFIRMED = "confirmed"
    PARTIAL = "partial"


class ReplenishmentRequest(BaseModel):
    request_id: str
    store_id: str
    items: Dict[str, int]
    status: RequestStatus = RequestStatus.PENDING
    wave_id: Optional[str] = None
    allocated_items: Dict[str, int] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class WaveStatus(str, Enum):
    DRAFT = "draft"
    PENDING_CONFIRM = "pending_confirm"
    CONFIRMED = "confirmed"
    EXPIRED = "expired"


class Wave(BaseModel):
    wave_id: str
    wave_number: int
    status: WaveStatus = WaveStatus.DRAFT
    store_ids: List[str] = Field(default_factory=list)
    request_ids: List[str] = Field(default_factory=list)
    items: Dict[str, int] = Field(default_factory=dict)
    expires_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
    confirmed_at: Optional[datetime] = None


class ChangeType(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    MOVED_IN = "moved_in"
    MOVED_OUT = "moved_out"
    QUANTITY_CHANGED = "quantity_changed"


class StoreChange(BaseModel):
    store_id: str
    change_type: ChangeType
    from_wave: Optional[str] = None
    to_wave: Optional[str] = None
    reason: str


class RearrangementRecord(BaseModel):
    rearrangement_id: str
    timestamp: datetime
    trigger: str
    before_waves: List[Wave]
    after_waves: List[Wave]
    store_changes: List[StoreChange]
    reason_summary: str
