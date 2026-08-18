"""
Pydantic request/response models. Field names mirror the DB schema
exactly (see CONTRACT.md / migrations/001_init_schema.sql) so the
frontend, scanner, and ml teams can rely on a stable shape.
"""
from pydantic import BaseModel
from typing import Optional, Any
from datetime import date, datetime


class DrugIn(BaseModel):
    name: str
    manufacturer: str
    gtin: str


class DrugOut(DrugIn):
    id: str
    created_at: datetime


class BatchIn(BaseModel):
    drug_id: str
    batch_number: str
    manufacture_date: date
    expiry_date: date


class BatchOut(BatchIn):
    id: str
    created_at: datetime


class ScanEventIn(BaseModel):
    batch_id: str
    node_type: str  # 'factory' | 'warehouse' | 'hospital' | 'vendor'
    node_id: str
    scanned_by: Optional[str] = None
    location: Optional[str] = None
    timestamp: Optional[datetime] = None
    raw_payload: Optional[dict[str, Any]] = None


class ScanEventOut(ScanEventIn):
    id: str
    created_at: datetime


class PurchaseOrderIn(BaseModel):
    vendor_id: str
    drug_id: str
    quantity: int
    status: str = "pending"  # 'pending' | 'shipped' | 'delivered'


class PurchaseOrderOut(PurchaseOrderIn):
    id: str
    created_at: datetime


class AnomalyOut(BaseModel):
    id: str
    batch_id: Optional[str]
    rule_triggered: str
    details: Optional[dict[str, Any]]
    resolved: bool
    created_at: datetime


class AlertOut(BaseModel):
    id: str
    type: str
    message: str
    recipient: str
    sent_at: Optional[datetime]
    channel: str
    created_at: datetime


class ForecastOut(BaseModel):
    drug: str
    dates: list[str]
    predicted_stock: list[float]
    reorder_threshold: Optional[float] = None
    predicted_stockout_date: Optional[str] = None


class ApiKeyCreateIn(BaseModel):
    owner_id: str
    scopes: list[str]


class ApiKeyCreateOut(BaseModel):
    id: str
    raw_key: str  # shown ONCE — caller must save it, we never show it again
    scopes: list[str]
