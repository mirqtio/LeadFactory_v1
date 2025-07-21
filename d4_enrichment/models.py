"""
Enrichment Models - Task 040

Data models for business enrichment results with confidence tracking,
source attribution, and data versioning.

Acceptance Criteria:
- Enrichment result model
- Match confidence tracking
- Source attribution
- Data versioning
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from database.base import UUID, Base


# UUID handling for both PostgreSQL and SQLite
def get_uuid_column():
    return Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def get_uuid_foreign_key(table_name):
    return Column(UUID(as_uuid=True), ForeignKey(f"{table_name}.id"), nullable=False)


class EnrichmentSource(Enum):
    """Sources of enrichment data"""

    CLEARBIT = "clearbit"
    HUNTER_IO = "hunter_io"
    APOLLO = "apollo"
    ZOOMINFO = "zoominfo"
    LINKEDIN = "linkedin"
    CRUNCHBASE = "crunchbase"
    FULLCONTACT = "fullcontact"
    INTERNAL = "internal"
    MANUAL = "manual"
    DATA_AXLE = "data_axle"  # Phase 0.5 addition


class MatchConfidence(Enum):
    """Confidence levels for data matching"""

    EXACT = "exact"  # 100% match
    HIGH = "high"  # 90-99% match
    MEDIUM = "medium"  # 70-89% match
    LOW = "low"  # 50-69% match
    UNCERTAIN = "uncertain"  # <50% match


class EnrichmentStatus(Enum):
    """Status of enrichment process"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIALLY_COMPLETED = "partially_completed"


@dataclass
class DataVersion:
    """
    Data versioning information

    Acceptance Criteria: Data versioning
    """

    version: str
    created_at: datetime
    source: EnrichmentSource
    checksum: str
    schema_version: str = "1.0"


class EnrichmentRequest(Base):
    """
    Request for business enrichment

    Tracks enrichment requests and their status
    """

    __tablename__ = "enrichment_requests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    business_id = Column(String(50), nullable=False, index=True)
    requested_sources = Column(JSON, nullable=False)  # List of sources to query
    priority = Column(String(20), default="medium")

    # Request metadata
    requested_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    requested_by = Column(String(100))  # User or system that requested
    deadline = Column(DateTime)  # Optional deadline

    # Status tracking
    status = Column(String(30), default=EnrichmentStatus.PENDING.value, nullable=False)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    failed_at = Column(DateTime)

    # Progress tracking
    total_sources = Column(Integer, default=0)
    completed_sources = Column(Integer, default=0)
    failed_sources = Column(Integer, default=0)

    # Configuration
    timeout_seconds = Column(Integer, default=300)
    retry_count = Column(Integer, default=2)
    include_contacts = Column(Boolean, default=True)
    include_company_details = Column(Boolean, default=True)
    include_financial_data = Column(Boolean, default=False)

    # Error tracking
    error_message = Column(Text)
    error_details = Column(JSON)

    # Relationships
    results = relationship("EnrichmentResult", back_populates="request", cascade="all, delete-orphan")

    # Indexing
    __table_args__ = (
        Index("idx_enrichment_requests_business_status", "business_id", "status"),
        Index("idx_enrichment_requests_requested_at", "requested_at"),
    )


class EnrichmentResult(Base):
    """
    Business enrichment result model

    Acceptance Criteria: Enrichment result model, Match confidence tracking,
    Source attribution, Data versioning
    """

    __tablename__ = "enrichment_results"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id = Column(String(36), ForeignKey("enrichment_requests.id"), nullable=False)
    business_id = Column(String(50), nullable=False, index=True)

    # Source attribution (Acceptance Criteria: Source attribution)
    source = Column(String(50), nullable=False)  # EnrichmentSource enum value
    source_record_id = Column(String(100))  # ID from external source
    source_url = Column(String(500))  # URL to source record

    # Match confidence tracking (Acceptance Criteria: Match confidence tracking)
    match_confidence = Column(String(20), nullable=False)  # MatchConfidence enum
    match_score = Column(Numeric(5, 4))  # 0.0000 to 1.0000
    match_criteria = Column(JSON)  # What fields were used for matching
    match_method = Column(String(50))  # Algorithm used for matching

    # Data versioning (Acceptance Criteria: Data versioning)
    data_version = Column(String(50), nullable=False)
    schema_version = Column(String(20), default="1.0")
    data_checksum = Column(String(64))  # Hash of enriched data

    # Timing
    enriched_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime)  # When this data should be refreshed

    # Company Information
    company_name = Column(String(200))
    legal_name = Column(String(200))
    domain = Column(String(100))
    website = Column(String(500))
    description = Column(Text)
    tagline = Column(String(500))

    # Business Details
    industry = Column(String(100))
    industry_code = Column(String(20))  # NAICS/SIC code
    company_type = Column(String(50))  # LLC, Inc, etc.
    employee_count = Column(Integer)
    employee_range = Column(String(50))  # "10-50", "50-100", etc.
    founded_year = Column(Integer)

    # Location
    headquarters_address = Column(JSON)  # Full address object
    headquarters_city = Column(String(100))
    headquarters_state = Column(String(50))
    headquarters_country = Column(String(50))
    headquarters_postal_code = Column(String(20))
    timezone = Column(String(50))

    # Financial Data
    annual_revenue = Column(Numeric(15, 2))
    revenue_range = Column(String(50))
    funding_total = Column(Numeric(15, 2))
    funding_stage = Column(String(50))
    valuation = Column(Numeric(15, 2))

    # Contact Information
    phone = Column(String(50))
    email_domain = Column(String(100))
    linkedin_url = Column(String(500))
    facebook_url = Column(String(500))
    twitter_url = Column(String(500))
    crunchbase_url = Column(String(500))

    # Technology Stack
    technologies = Column(JSON)  # Array of technologies used
    integrations = Column(JSON)  # Array of integrations/tools

    # Additional Metadata
    logo_url = Column(String(500))
    parent_company = Column(String(200))
    subsidiaries = Column(JSON)  # Array of subsidiary companies
    tags = Column(JSON)  # Array of classification tags

    # Quality Metrics
    data_quality_score = Column(Numeric(3, 2))  # 0.00 to 1.00
    completeness_score = Column(Numeric(3, 2))  # 0.00 to 1.00
    freshness_days = Column(Integer)  # How old is this data

    # Raw Data Storage
    raw_data = Column(JSON)  # Original response from source
    processed_data = Column(JSON)  # Cleaned/normalized data

    # Status and Validation
    is_validated = Column(Boolean, default=False)
    validation_errors = Column(JSON)  # Array of validation issues
    is_active = Column(Boolean, default=True)

    # Cost Tracking
    enrichment_cost_usd = Column(Numeric(10, 4), default=0)
    api_calls_used = Column(Integer, default=1)

    # Relationships
    request = relationship("EnrichmentRequest", back_populates="results")

    # Indexing for performance
    __table_args__ = (
        Index("idx_enrichment_results_business_source", "business_id", "source"),
        Index("idx_enrichment_results_confidence", "match_confidence"),
        Index("idx_enrichment_results_enriched_at", "enriched_at"),
        Index("idx_enrichment_results_expires_at", "expires_at"),
        Index("idx_enrichment_results_company_name", "company_name"),
        Index("idx_enrichment_results_domain", "domain"),
        UniqueConstraint("business_id", "source", "data_version", name="uq_business_source_version"),
    )

    def __repr__(self):
        return f"<EnrichmentResult(business_id='{self.business_id}', source='{self.source}', confidence='{self.match_confidence}')>"

    @property
    def is_expired(self) -> bool:
        """Check if enrichment data has expired"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at

    @property
    def age_days(self) -> int:
        """Get age of enrichment data in days"""
        return (datetime.utcnow() - self.enriched_at).days

    def get_address_string(self) -> str | None:
        """Get formatted address string"""
        if not self.headquarters_address:
            return None

        addr = self.headquarters_address
        parts = []

        if addr.get("street"):
            parts.append(addr["street"])
        if addr.get("city"):
            parts.append(addr["city"])
        if addr.get("state"):
            parts.append(addr["state"])
        if addr.get("postal_code"):
            parts.append(addr["postal_code"])
        if addr.get("country"):
            parts.append(addr["country"])

        return ", ".join(parts) if parts else None

    def get_contact_info(self) -> dict[str, Any]:
        """Get consolidated contact information"""
        return {
            "phone": self.phone,
            "email_domain": self.email_domain,
            "website": self.website,
            "linkedin": self.linkedin_url,
            "address": self.get_address_string(),
        }

    def get_company_metrics(self) -> dict[str, Any]:
        """Get company size and financial metrics"""
        return {
            "employee_count": self.employee_count,
            "employee_range": self.employee_range,
            "annual_revenue": float(self.annual_revenue) if self.annual_revenue else None,
            "revenue_range": self.revenue_range,
            "funding_total": float(self.funding_total) if self.funding_total else None,
            "founded_year": self.founded_year,
        }

    def get_data_quality_metrics(self) -> dict[str, Any]:
        """Get data quality assessment metrics"""
        return {
            "match_confidence": self.match_confidence,
            "match_score": float(self.match_score) if self.match_score else None,
            "data_quality_score": float(self.data_quality_score) if self.data_quality_score else None,
            "completeness_score": float(self.completeness_score) if self.completeness_score else None,
            "freshness_days": self.freshness_days,
            "age_days": self.age_days,
            "is_expired": self.is_expired,
        }

    def update_data_version(self, new_data: dict[str, Any]) -> str:
        """
        Update data version when enrichment data changes

        Acceptance Criteria: Data versioning
        """
        import hashlib
        import json

        def decimal_converter(obj):
            """Convert Decimal objects to float for JSON serialization"""
            if isinstance(obj, Decimal):
                return float(obj)
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        # Generate new version based on timestamp and content
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        content_hash = hashlib.md5(
            json.dumps(new_data, sort_keys=True, default=decimal_converter).encode()
        ).hexdigest()[:8]

        new_version = f"{timestamp}_{content_hash}"

        # Update version and checksum
        self.data_version = new_version
        self.data_checksum = hashlib.sha256(
            json.dumps(new_data, sort_keys=True, default=decimal_converter).encode()
        ).hexdigest()

        return new_version

    def calculate_match_score(self, input_data: dict[str, Any], matched_data: dict[str, Any]) -> float:
        """
        Calculate match confidence score

        Acceptance Criteria: Match confidence tracking
        """
        total_weight = 0
        matched_weight = 0

        # Define field weights for matching
        field_weights = {
            "company_name": 0.4,
            "domain": 0.3,
            "phone": 0.2,
            "address": 0.1,
        }

        for field, weight in field_weights.items():
            total_weight += weight

            input_val = str(input_data.get(field, "")).lower().strip()
            matched_val = str(matched_data.get(field, "")).lower().strip()

            if input_val and matched_val:
                # Simple string similarity check
                if input_val == matched_val:
                    matched_weight += weight
                elif input_val in matched_val or matched_val in input_val:
                    matched_weight += weight * 0.8
                elif self._strings_similar(input_val, matched_val):
                    matched_weight += weight * 0.6

        return matched_weight / total_weight if total_weight > 0 else 0.0

    def _strings_similar(self, str1: str, str2: str, threshold: float = 0.8) -> bool:
        """Simple string similarity check"""
        if not str1 or not str2:
            return False

        # Basic Jaccard similarity using words
        words1 = set(str1.split())
        words2 = set(str2.split())

        if not words1 or not words2:
            return False

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        similarity = len(intersection) / len(union)
        return similarity >= threshold

    def set_match_confidence(self) -> None:
        """
        Set match confidence enum based on match score

        Acceptance Criteria: Match confidence tracking
        """
        if not self.match_score:
            self.match_confidence = MatchConfidence.UNCERTAIN.value
            return

        score = float(self.match_score)

        if score >= 1.0:
            self.match_confidence = MatchConfidence.EXACT.value
        elif score >= 0.9:
            self.match_confidence = MatchConfidence.HIGH.value
        elif score >= 0.7:
            self.match_confidence = MatchConfidence.MEDIUM.value
        elif score >= 0.5:
            self.match_confidence = MatchConfidence.LOW.value
        else:
            self.match_confidence = MatchConfidence.UNCERTAIN.value


class EnrichmentAuditLog(Base):
    """
    Audit log for enrichment operations

    Tracks all enrichment activities for compliance and debugging
    """

    __tablename__ = "enrichment_audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    business_id = Column(String(50), nullable=False, index=True)
    request_id = Column(String(36), ForeignKey("enrichment_requests.id"))

    # Action details
    action = Column(String(50), nullable=False)  # "enrich", "update", "delete", etc.
    source = Column(String(50), nullable=False)
    user_id = Column(String(50))  # User who initiated action

    # Data changes
    old_values = Column(JSON)  # Previous values
    new_values = Column(JSON)  # New values
    changes = Column(JSON)  # Summary of what changed

    # Metadata
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    ip_address = Column(String(45))  # IPv4 or IPv6
    user_agent = Column(String(500))
    session_id = Column(String(100))

    # Cost tracking
    api_cost_usd = Column(Numeric(10, 4), default=0)

    # Indexing
    __table_args__ = (
        Index("idx_enrichment_audit_business_timestamp", "business_id", "timestamp"),
        Index("idx_enrichment_audit_action", "action"),
        Index("idx_enrichment_audit_source", "source"),
    )


# Data quality validation functions
def validate_enrichment_data(data: dict[str, Any]) -> list[str]:
    """
    Validate enrichment data quality

    Returns list of validation errors
    """
    errors = []

    # Required fields validation
    if not data.get("company_name"):
        errors.append("Company name is required")

    # Domain validation
    domain = data.get("domain")
    if domain and not _is_valid_domain(domain):
        errors.append(f"Invalid domain format: {domain}")

    # Email validation
    email_domain = data.get("email_domain")
    if email_domain and not _is_valid_domain(email_domain):
        errors.append(f"Invalid email domain format: {email_domain}")

    # Phone validation
    phone = data.get("phone")
    if phone and not _is_valid_phone(phone):
        errors.append(f"Invalid phone format: {phone}")

    # Employee count validation
    employee_count = data.get("employee_count")
    if employee_count is not None and (employee_count < 0 or employee_count > 1000000):
        errors.append(f"Invalid employee count: {employee_count}")

    # Revenue validation
    revenue = data.get("annual_revenue")
    if revenue is not None and revenue < 0:
        errors.append(f"Invalid annual revenue: {revenue}")

    return errors


def _is_valid_domain(domain: str) -> bool:
    """Basic domain validation"""
    import re

    pattern = r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.([a-zA-Z]{2,}\.)*[a-zA-Z]{2,}$"
    return bool(re.match(pattern, domain))


def _is_valid_phone(phone: str) -> bool:
    """Basic phone number validation"""
    import re

    # Remove all non-digit characters
    digits = re.sub(r"\D", "", phone)
    # Check if we have 10-15 digits (international format)
    return 10 <= len(digits) <= 15


def calculate_completeness_score(data: dict[str, Any]) -> float:
    """
    Calculate data completeness score

    Returns score from 0.0 to 1.0 based on how many fields are populated
    """
    # Define core fields and their weights
    core_fields = {
        "company_name": 0.15,
        "domain": 0.15,
        "industry": 0.10,
        "employee_count": 0.10,
        "headquarters_city": 0.10,
        "headquarters_state": 0.05,
        "headquarters_country": 0.05,
        "phone": 0.08,
        "description": 0.07,
        "founded_year": 0.05,
        "website": 0.05,
        "annual_revenue": 0.05,
    }

    total_weight = sum(core_fields.values())
    achieved_weight = 0

    for field, weight in core_fields.items():
        value = data.get(field)
        if value is not None and str(value).strip():
            achieved_weight += weight

    return achieved_weight / total_weight if total_weight > 0 else 0.0
