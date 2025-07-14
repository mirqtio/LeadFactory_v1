"""
Hunter.io API stub endpoints
"""
import random
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

router = APIRouter()


@router.get("/v2/email-finder")
async def find_email(
    api_key: str = Query(...),
    domain: Optional[str] = Query(None),
    company: Optional[str] = Query(None),
    first_name: Optional[str] = Query(None),
    last_name: Optional[str] = Query(None),
):
    """Stub endpoint for Hunter.io email finder"""

    # Check API key
    if not api_key or api_key == "invalid":
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Simulate rate limiting (1 in 30 requests)
    if random.random() < 0.033:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "3600"},
        )

    # Require either domain or company
    if not domain and not company:
        raise HTTPException(status_code=400, detail="Either domain or company is required")

    # Simulate no email found (20% of requests)
    if random.random() < 0.2:
        return {
            "data": {
                "email": None,
                "score": 0,
            }
        }

    # Generate email based on inputs
    email_domain = domain or f"{company.lower().replace(' ', '')}.com"

    if first_name and last_name:
        # Use provided names
        patterns = [
            f"{first_name.lower()}.{last_name.lower()}@{email_domain}",
            f"{first_name.lower()[0]}{last_name.lower()}@{email_domain}",
            f"{first_name.lower()}@{email_domain}",
        ]
        email = random.choice(patterns)
    else:
        # Generic emails
        departments = ["info", "contact", "hello", "sales", "support"]
        email = f"{random.choice(departments)}@{email_domain}"

    # Generate realistic data
    return {
        "data": {
            "email": email,
            "score": random.randint(70, 99),  # Confidence score
            "domain": email_domain,
            "first_name": first_name,
            "last_name": last_name,
            "position": random.choice(["CEO", "Manager", "Director", "Owner", None]),
            "twitter": f"https://twitter.com/{company.lower().replace(' ', '')}" if random.random() > 0.5 else None,
            "linkedin_url": f"https://linkedin.com/in/{first_name}-{last_name}".lower()
            if first_name and last_name and random.random() > 0.3
            else None,
            "sources": [
                {
                    "domain": email_domain,
                    "uri": f"https://{email_domain}/about",
                    "extracted_on": "2024-01-15",
                    "still_on_page": True,
                }
            ]
            if random.random() > 0.4
            else [],
        },
        "meta": {
            "results": 1,
            "limit": 50,
            "offset": 0,
            "params": {
                "domain": domain,
                "company": company,
                "first_name": first_name,
                "last_name": last_name,
            },
        },
    }


@router.get("/v2/account")
async def account_info(api_key: str = Query(...)):
    """Stub endpoint for Hunter.io account info"""

    if not api_key or api_key == "invalid":
        raise HTTPException(status_code=401, detail="Invalid API key")

    return {
        "data": {
            "email": "test@example.com",
            "plan_name": "Free",
            "plan_level": 0,
            "reset_date": "2024-02-01",
            "team_id": 12345,
            "calls": {
                "used": random.randint(5, 20),
                "available": 25,
            },
        }
    }
