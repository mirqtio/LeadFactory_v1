"""
Simple Campaign model for orchestration
"""
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON
from sqlalchemy.sql import func
from database.base import Base

class SimpleCampaign(Base):
    """Simple campaign model for orchestration"""
    __tablename__ = "campaigns"
    __table_args__ = {'extend_existing': True}
    
    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    vertical = Column(String(50), nullable=False)
    geo_targets = Column(JSON, nullable=False)  # PostgreSQL supports JSON
    daily_quota = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default='draft')
    created_at = Column(DateTime, nullable=False, server_default=func.now())