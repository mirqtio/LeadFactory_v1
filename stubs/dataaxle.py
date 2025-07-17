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


@router.post("/business/match", response_model=BusinessMatchResponse)
async def match_business(request: BusinessMatchRequest, authorization: str = Header(None)):
    """Stub endpoint for Data Axle business match"""

    # Check authorization
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Handle special test cases
    if request.business_name == "TRIGGER_ERROR":
        raise HTTPException(status_code=500, detail="Internal server error")
    
    if request.business_name == "Nonexistent Business XYZ":
        return BusinessMatchResponse(match_found=False, match_confidence=0.0, business_data={})
    
    # Simulate rate limiting (1 in 50 requests) - disabled for specific test businesses
    if request.business_name not in ["Test Restaurant LLC", "Minimal Business"] and random.random() < 0.02:
        raise HTTPException(status_code=429, detail="Rate limit exceeded", headers={"Retry-After": "60"})

    # List of test businesses that should always return data
    test_businesses = ["Test Restaurant LLC", "Minimal Business"] + [f"Test Business {i}" for i in range(10)]
    
    # Simulate no match found (20% of requests) - disabled for test businesses
    if request.business_name not in test_businesses and random.random() < 0.2:
        return BusinessMatchResponse(match_found=False, match_confidence=0.0, business_data={})

    # Generate realistic business data
    # For Test Restaurant LLC, return specific expected data
    if request.business_name == "Test Restaurant LLC":
        business_data = {
            "business_id": "DA123456",
            "emails": [
                {
                    "email": "contact@restaurant.com",
                    "type": "primary",
                },
            ],
            "phones": [
                {"number": "+14155551234", "type": "main"},
            ],
            "website": "https://www.restaurant.com",
            "employee_count": 25,
            "annual_revenue": 2500000,
            "years_in_business": 10,
            "business_type": "LLC",
            "sic_codes": ["5812"],
            "naics_codes": ["722511"],
            "match_confidence": 0.95,
        }
    elif request.business_name == "Minimal Business":
        # Always return data with emails and phones for Minimal Business
        business_data = {
            "business_id": "DA_MINIMAL",
            "emails": [{"email": "contact@minimalbusiness.com", "type": "primary"}],
            "phones": [{"number": "+15555555555", "type": "main"}],
            "website": None,
            "employee_count": 5,
            "annual_revenue": 100000,
            "years_in_business": 2,
            "business_type": "LLC",
            "sic_codes": ["9999"],
            "naics_codes": ["999999"],
            "match_confidence": 0.85,
        }
    elif request.business_name.startswith("Test Business "):
        # Consistent data for Test Business N
        idx = request.business_name.replace("Test Business ", "")
        business_data = {
            "business_id": f"DA_TEST_{idx}",
            "emails": [{"email": f"test{idx}@business.com", "type": "primary"}],
            "phones": [{"number": f"+1555000{idx.zfill(4)}", "type": "main"}],
            "website": f"https://testbusiness{idx}.com",
            "employee_count": 10,
            "annual_revenue": 500000,
            "years_in_business": 5,
            "business_type": "LLC",
            "sic_codes": ["1234"],
            "naics_codes": ["123456"],
            "match_confidence": 0.90,
        }
    else:
        # Default business data generation
        business_data = {
            "business_id": f"DA_{random.randint(1000000, 9999999)}",
            "emails": [
                {
                    "email": f"contact@{request.business_name.lower().replace(' ', '')}.com",
                    "type": "primary",
                },
                {
                    "email": f"info@{request.business_name.lower().replace(' ', '')}.com",
                    "type": "general",
                },
            ],
            "phones": [
                {"number": f"+1{random.randint(2000000000, 9999999999)}", "type": "main"},
                {"number": f"+1{random.randint(2000000000, 9999999999)}", "type": "mobile"},
            ],
            "website": f"https://www.{request.business_name.lower().replace(' ', '')}.com"
            if random.random() > 0.4
            else None,  # 60% have websites
            "employee_count": random.choice([1, 5, 10, 25, 50, 100, 250, 500]),
            "annual_revenue": random.choice([100000, 500000, 1000000, 5000000, 10000000]),
            "years_in_business": random.randint(1, 50),
            "business_type": random.choice(["LLC", "Corporation", "Partnership", "Sole Proprietorship"]),
            "sic_codes": [str(random.randint(1000, 9999))],
            "naics_codes": [str(random.randint(100000, 999999))],
            "match_confidence": round(random.uniform(0.8, 0.99), 2),
        }

    return BusinessMatchResponse(
        match_found=True,
        match_confidence=business_data["match_confidence"],
        business_data=business_data,
    )


@router.get("/account/status")
async def account_status(authorization: str = Header(None)):
    """Stub endpoint for account status check"""

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Special case for invalid-key test
    if authorization == "Bearer invalid-key":
        raise HTTPException(status_code=401, detail="Invalid API key")

    return {
        "status": "active",
        "credits_remaining": random.randint(1000, 10000),
        "rate_limit": 200,
        "rate_limit_remaining": random.randint(50, 200),
    }


@router.get("/company/enrich")
async def enrich_company(domain: str, fields: str = "", authorization: str = Header(None)):
    """Stub endpoint for company enrichment by domain"""
    
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Special test case for testcompany.com
    if domain == "testcompany.com":
        return {
            "domain": domain,
            "email": "info@testcompany.com",
            "phone": "+15555551234",
            "employee_count": 50,
            "annual_revenue": 5000000,
            "website": f"https://{domain}",
            "business_type": "Corporation",
        }
    
    # Default enrichment response
    return {
        "domain": domain,
        "email": f"contact@{domain}",
        "phone": f"+1{random.randint(2000000000, 9999999999)}",
        "employee_count": random.choice([10, 50, 100, 500]),
        "annual_revenue": random.choice([1000000, 5000000, 10000000]),
        "website": f"https://{domain}",
        "business_type": random.choice(["LLC", "Corporation"]),
    }
