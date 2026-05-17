from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MaterialType(str, Enum):
    PRINTED_BOOK = "printed_book"
    EBOOK = "ebook"
    AUDIOBOOK = "audiobook"
    MAGAZINE = "magazine"
    DISSERTATION = "dissertation"


class ReservationStatus(str, Enum):
    WAITING = "waiting"
    READY = "ready"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"


class NotificationChannel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    TELEGRAM = "telegram"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Role(str, Enum):
    READER = "reader"
    LIBRARIAN = "librarian"
    ADMIN = "admin"
    SYSTEM = "system"


class DemandEventType(str, Enum):
    SEARCH = "search"
    CHECKOUT = "checkout"
    RESERVATION = "reservation"
    VIEW = "view"


class ClassificationCode(BaseModel):
    udc: str = Field(min_length=1)
    bbk: str = Field(min_length=1)


class CatalogMaterialCreateRequest(BaseModel):
    title: str = Field(min_length=1)
    authors: list[str] = Field(default_factory=list)
    material_type: MaterialType
    isbn: str | None = None
    publication_year: int | None = None
    language: str = "ru"
    classification: ClassificationCode
    copies_total: int = Field(ge=1, default=1)
    shelf_code: str | None = None
    tags: list[str] = Field(default_factory=list)
    description: str = ""


class CatalogMaterialUpdateRequest(BaseModel):
    title: str | None = None
    authors: list[str] | None = None
    isbn: str | None = None
    publication_year: int | None = None
    language: str | None = None
    classification: ClassificationCode | None = None
    copies_total: int | None = Field(default=None, ge=1)
    shelf_code: str | None = None
    tags: list[str] | None = None
    description: str | None = None


class CatalogMaterial(BaseModel):
    material_id: str
    title: str
    authors: list[str]
    material_type: MaterialType
    isbn: str | None = None
    publication_year: int | None = None
    language: str = "ru"
    classification: ClassificationCode
    copies_total: int = Field(ge=1)
    copies_available: int = Field(ge=0)
    shelf_code: str | None = None
    tags: list[str] = Field(default_factory=list)
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PatronRegisterRequest(BaseModel):
    full_name: str = Field(min_length=3)
    email: str = Field(min_length=5)
    phone: str = Field(min_length=5)


class Patron(BaseModel):
    patron_id: str
    full_name: str
    email: str
    phone: str
    e_card_number: str
    registered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    blocked: bool = False


class LoanCheckoutRequest(BaseModel):
    patron_id: str
    material_id: str
    loan_days: int = Field(default=14, ge=1, le=90)
    actor_id: str
    actor_role: Role


class LoanRenewRequest(BaseModel):
    extension_days: int = Field(default=14, ge=1, le=30)
    actor_id: str
    actor_role: Role


class LoanReturnRequest(BaseModel):
    returned_at: datetime | None = None
    actor_id: str
    actor_role: Role


class LoanRecord(BaseModel):
    loan_id: str
    patron_id: str
    material_id: str
    checkout_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    due_date: datetime
    returned_at: datetime | None = None
    renewals: int = 0
    fine_rub: float = 0.0
    status: str = "active"


class DebtSummary(BaseModel):
    patron_id: str
    total_debt_rub: float = 0.0
    overdue_loans: int = 0


class ReservationCreateRequest(BaseModel):
    patron_id: str
    material_id: str
    pickup_branch: str
    actor_id: str
    actor_role: Role


class Reservation(BaseModel):
    reservation_id: str
    patron_id: str
    material_id: str
    pickup_branch: str
    status: ReservationStatus = ReservationStatus.WAITING
    queue_position: int = 1
    notified_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EbookUploadRequest(BaseModel):
    material_id: str
    title: str
    author: str
    file_name: str
    content_text: str = ""
    drm_watermark: bool = True
    actor_id: str
    actor_role: Role


class EbookAsset(BaseModel):
    asset_id: str
    material_id: str
    title: str
    author: str
    file_name: str
    storage_key: str
    drm_fingerprint: str
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EbookAccessGrantRequest(BaseModel):
    asset_id: str
    patron_id: str
    minutes: int = Field(default=60, ge=5, le=360)
    actor_id: str
    actor_role: Role


class EbookAccessToken(BaseModel):
    token: str
    asset_id: str
    patron_id: str
    expires_at: datetime


class EbookReadRequest(BaseModel):
    token: str


class VisitEvent(BaseModel):
    branch_id: str
    patron_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DemandEvent(BaseModel):
    material_id: str
    event_type: DemandEventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class InventorySnapshot(BaseModel):
    material_type: MaterialType
    total_titles: int = Field(ge=0)
    copies_total: int = Field(ge=0)
    copies_available: int = Field(ge=0)
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ServiceMetric(BaseModel):
    metric: str
    value: float
    target: float
    unit: str


class AuditEvent(BaseModel):
    event_id: str
    actor_id: str
    actor_role: Role | str
    action: str
    object_type: str
    object_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CheckoutWorkflowResult(BaseModel):
    material: dict[str, Any]
    debt: dict[str, Any]
    loan: dict[str, Any]
    notification: dict[str, Any]
    completed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
