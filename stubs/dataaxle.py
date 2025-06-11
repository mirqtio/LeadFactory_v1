"""
Data Axle API stub endpoints
"""
import random
from typing import Any, Dict

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

router = APIRouter()


class BusinessMatchRequest(BaseModel):
    """Business match request model"""
    business_name: str
    address: str = ""
    city: str = ""
    state: str = ""
    zip: str = ""
    match_threshold: float = 0.8
    return_fields: list = []


class BusinessMatchResponse(BaseModel):
    """Business match response model"""
    match_found: bool
    match_confidence: float
    business_data: Dict[str, Any]


@router.post("/v2/business/match", response_model=BusinessMatchResponse)
async def match_business(
    request: BusinessMatchRequest,
    authorization: str = Header(None)
):
    """Stub endpoint for Data Axle business match"""
    
    # Check authorization
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    # Simulate rate limiting (1 in 50 requests)
    if random.random() < 0.02:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": "60"}
        )
    
    # Simulate no match found (20% of requests)
    if random.random() < 0.2:
        return BusinessMatchResponse(
            match_found=False,
            match_confidence=0.0,
            business_data={}
        )
    
    # Generate realistic business data
    business_data = {
        "business_id": f"DA_{random.randint(1000000, 9999999)}",
        "emails": [
            {"email": f"contact@{request.business_name.lower().replace(' ', '')}.com", "type": "primary"},
            {"email": f"info@{request.business_name.lower().replace(' ', '')}.com", "type": "general"}
        ] if random.random() > 0.3 else [],  # 70% have emails
        "phones": [
            {"number": f"+1{random.randint(2000000000, 9999999999)}", "type": "main"},
            {"number": f"+1{random.randint(2000000000, 9999999999)}", "type": "mobile"}
        ] if random.random() > 0.1 else [],  # 90% have phones
        "website": f"https://www.{request.business_name.lower().replace(' ', '')}.com" 
            if random.random() > 0.4 else None,  # 60% have websites
        "employee_count": random.choice([1, 5, 10, 25, 50, 100, 250, 500]),
        "annual_revenue": random.choice([100000, 500000, 1000000, 5000000, 10000000]),
        "years_in_business": random.randint(1, 50),
        "business_type": random.choice(["LLC", "Corporation", "Partnership", "Sole Proprietorship"]),
        "sic_codes": [str(random.randint(1000, 9999))],
        "naics_codes": [str(random.randint(100000, 999999))],
        "match_confidence": round(random.uniform(0.8, 0.99), 2)
    }
    
    return BusinessMatchResponse(
        match_found=True,
        match_confidence=business_data["match_confidence"],
        business_data=business_data
    )


@router.get("/v2/account/status")
async def account_status(authorization: str = Header(None)):
    """Stub endpoint for account status check"""
    
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    return {
        "status": "active",
        "credits_remaining": random.randint(1000, 10000),
        "rate_limit": 200,
        "rate_limit_remaining": random.randint(50, 200)
    }