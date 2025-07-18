"""
Stub server to mock external APIs for testing
Implements Google PageSpeed, Stripe, SendGrid, OpenAI, Data Axle, and Hunter endpoints
"""
import json
import os
import random
from datetime import datetime
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Import Data Axle and Hunter stub routers
from stubs.dataaxle import router as dataaxle_router
from stubs.hunter import router as hunter_router

app = FastAPI(title="LeadFactory Stub Server", version="1.0.0")

# Include Data Axle routes
app.include_router(dataaxle_router, prefix="")
# Include Hunter routes
app.include_router(hunter_router, prefix="")

# Configuration
USE_STUBS = os.getenv("USE_STUBS", "true").lower() == "true"
STUB_DELAY_MS = int(os.getenv("STUB_DELAY_MS", "50"))
IS_TEST_MODE = os.getenv("ENVIRONMENT") == "test"


# Stub data generators
def generate_pagespeed_data(url: str) -> Dict[str, Any]:
    """Generate realistic PageSpeed Insights data"""
    # Simulate some URLs being slower than others
    is_slow = random.random() < 0.3

    performance_score = random.uniform(0.2, 0.5) if is_slow else random.uniform(0.6, 0.95)
    seo_score = random.uniform(0.5, 0.95)

    return {
        "captchaResult": "CAPTCHA_NOT_NEEDED",
        "kind": "pagespeedonline#result",
        "id": url,
        "loadingExperience": {
            "id": url,
            "metrics": {
                "CUMULATIVE_LAYOUT_SHIFT_SCORE": {
                    "percentile": random.randint(5, 25) if is_slow else random.randint(1, 10),
                    "distributions": [],
                },
                "FIRST_CONTENTFUL_PAINT_MS": {
                    "percentile": random.randint(2000, 5000) if is_slow else random.randint(800, 2000),
                    "distributions": [],
                },
                "FIRST_INPUT_DELAY_MS": {
                    "percentile": random.randint(100, 300) if is_slow else random.randint(20, 100),
                    "distributions": [],
                },
                "LARGEST_CONTENTFUL_PAINT_MS": {
                    "percentile": random.randint(3000, 8000) if is_slow else random.randint(1000, 3000),
                    "distributions": [],
                },
            },
            "overall_category": "SLOW" if is_slow else "FAST",
        },
        "lighthouseResult": {
            "requestedUrl": url,
            "finalUrl": url,
            "lighthouseVersion": "11.0.0",
            "userAgent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            "fetchTime": datetime.utcnow().isoformat() + "Z",
            "environment": {
                "networkUserAgent": "",
                "hostUserAgent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                "benchmarkIndex": 1500,
            },
            "categories": {
                "performance": {
                    "id": "performance",
                    "title": "Performance",
                    "score": performance_score,
                },
                "accessibility": {
                    "id": "accessibility",
                    "title": "Accessibility",
                    "score": random.uniform(0.7, 0.95),
                },
                "best-practices": {
                    "id": "best-practices",
                    "title": "Best Practices",
                    "score": random.uniform(0.6, 0.9),
                },
                "seo": {"id": "seo", "title": "SEO", "score": seo_score},
            },
            "audits": {
                "largest-contentful-paint": {
                    "id": "largest-contentful-paint",
                    "title": "Largest Contentful Paint",
                    "description": "Marks the time at which the largest text or image is painted",
                    "score": 0.2 if is_slow else 0.9,
                    "displayValue": f"{random.randint(3, 8) if is_slow else random.uniform(0.8, 2.5):.1f} s",
                    "numericValue": random.randint(3000, 8000) if is_slow else random.randint(800, 2500),
                    "numericUnit": "millisecond",
                },
                "max-potential-fid": {
                    "id": "max-potential-fid",
                    "title": "Max Potential First Input Delay",
                    "description": "The maximum potential First Input Delay that your users could experience",
                    "score": 0.5 if is_slow else 0.95,
                    "displayValue": f"{random.randint(100, 300) if is_slow else random.randint(16, 100)} ms",
                    "numericValue": random.randint(100, 300) if is_slow else random.randint(16, 100),
                    "numericUnit": "millisecond",
                },
                "cumulative-layout-shift": {
                    "id": "cumulative-layout-shift",
                    "title": "Cumulative Layout Shift",
                    "description": "Measures the movement of visible elements within the viewport",
                    "score": 0.7 if is_slow else 0.95,
                    "displayValue": str(
                        round(
                            random.uniform(0.1, 0.3) if is_slow else random.uniform(0, 0.1),
                            3,
                        )
                    ),
                    "numericValue": random.uniform(0.1, 0.3) if is_slow else random.uniform(0, 0.1),
                    "numericUnit": "unitless",
                },
            },
        },
    }


# ScreenshotOne API endpoints
@app.get("/take")
async def screenshotone_take(
    url: str,
    full_page: str = "true",
    viewport_width: int = 1920,
    viewport_height: int = 1080,
    device_scale_factor: int = 1,
    format: str = "png",
    access_key: Optional[str] = None,
    signature: Optional[str] = None,
    **kwargs,
):
    """Mock ScreenshotOne API"""
    if not USE_STUBS:
        raise HTTPException(status_code=503, detail="Stub server disabled")

    # Generate stub screenshot URL
    timestamp = int(datetime.utcnow().timestamp())
    screenshot_url = f"https://images.screenshotone.com/stub/{timestamp}_screenshot.{format}"

    return {
        "screenshot_url": screenshot_url,
        "screenshot_thumb_url": f"https://images.screenshotone.com/stub/{timestamp}_thumb.{format}",
        "success": True,
        "cached": random.choice([True, False]),
        "format": format,
    }


# Google Places API endpoints
@app.get("/maps/api/place/findplacefromtext/json")
async def google_places_find(
    input: str, inputtype: str = "textquery", fields: Optional[str] = None, key: Optional[str] = None
):
    """Mock Google Places Find Place API"""
    if not USE_STUBS:
        raise HTTPException(status_code=503, detail="Stub server disabled")

    # Generate stub place data
    place_id = f"ChIJ_stub_{datetime.utcnow().timestamp()}"

    return {
        "candidates": [
            {
                "place_id": place_id,
                "name": input.split(",")[0],  # Use first part as name
                "formatted_address": f"123 Main St, {input}",
            }
        ],
        "status": "OK",
    }


@app.get("/maps/api/place/details/json")
async def google_places_details(place_id: str, fields: Optional[str] = None, key: Optional[str] = None):
    """Mock Google Places Details API"""
    if not USE_STUBS:
        raise HTTPException(status_code=503, detail="Stub server disabled")

    # Handle invalid place IDs
    if "Invalid" in place_id or place_id == "InvalidPlaceID123":
        return {
            "error_message": "Invalid place_id provided",
            "status": "INVALID_REQUEST",
        }

    # Generate realistic business data
    has_hours = random.random() > 0.2  # 80% have hours

    details = {
        "result": {
            "place_id": place_id,
            "name": "Example Business",
            "formatted_address": "123 Main St, Anytown, USA 12345",
            "formatted_phone_number": "(555) 123-4567",
            "website": "https://example-business.com",
            "business_status": "OPERATIONAL",
            "rating": round(random.uniform(3.5, 5.0), 1),
            "user_ratings_total": random.randint(10, 500),
            "types": ["restaurant", "food", "point_of_interest", "establishment"],
        },
        "status": "OK",
    }

    # Add opening hours if available
    if has_hours:
        details["result"]["opening_hours"] = {
            "open_now": random.choice([True, False]),
            "weekday_text": [
                "Monday: 9:00 AM – 5:00 PM",
                "Tuesday: 9:00 AM – 5:00 PM",
                "Wednesday: 9:00 AM – 5:00 PM",
                "Thursday: 9:00 AM – 5:00 PM",
                "Friday: 9:00 AM – 5:00 PM",
                "Saturday: 10:00 AM – 3:00 PM",
                "Sunday: Closed",
            ],
        }

    return details


# Google PageSpeed Insights endpoints
@app.get("/pagespeedonline/v5/runPagespeed")
async def pagespeed_analyze(url: str, strategy: str = "mobile", key: Optional[str] = None):
    """Mock Google PageSpeed Insights API"""
    if not USE_STUBS:
        raise HTTPException(status_code=503, detail="Stub server disabled")

    # Simulate some URLs failing (disabled in test mode)
    if not IS_TEST_MODE and random.random() < 0.05:  # 5% failure rate
        return JSONResponse(status_code=400, content={"error": {"message": "Invalid URL"}})

    return generate_pagespeed_data(url)


# Stripe endpoints
class StripeCheckoutSession(BaseModel):
    payment_method_types: List[str]
    line_items: List[Dict[str, Any]]
    mode: str
    success_url: str
    cancel_url: str
    client_reference_id: Optional[str] = None
    customer_email: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@app.post("/v1/checkout/sessions")
async def stripe_create_checkout(session: StripeCheckoutSession, authorization: str = Header(None)):
    """Mock Stripe Checkout Session creation"""
    if not USE_STUBS:
        raise HTTPException(status_code=503, detail="Stub server disabled")

    session_id = f"cs_test_stub_{datetime.utcnow().timestamp()}"

    return {
        "id": session_id,
        "object": "checkout.session",
        "cancel_url": session.cancel_url,
        "client_reference_id": session.client_reference_id,
        "created": int(datetime.utcnow().timestamp()),
        "currency": "usd",
        "customer": None,
        "customer_email": session.customer_email,
        "livemode": False,
        "metadata": session.metadata or {},
        "mode": session.mode,
        "payment_intent": f"pi_test_stub_{datetime.utcnow().timestamp()}",
        "payment_method_types": session.payment_method_types,
        "payment_status": "unpaid",
        "status": "open",
        "success_url": session.success_url,
        "url": f"https://checkout.stripe.com/pay/{session_id}",
    }


# SendGrid endpoints
class SendGridMail(BaseModel):
    personalizations: List[Dict[str, Any]]
    from_email: Dict[str, Any]  # Allow name field
    subject: str
    content: List[Dict[str, str]]


@app.post("/v3/mail/send")
async def sendgrid_send(mail: SendGridMail, authorization: str = Header(None)):
    """Mock SendGrid mail send"""
    if not USE_STUBS:
        raise HTTPException(status_code=503, detail="Stub server disabled")

    # Simulate some emails bouncing
    if random.random() < 0.02:  # 2% bounce rate
        return JSONResponse(status_code=400, content={"errors": [{"message": "Invalid email address"}]})

    return Response(
        status_code=202,
        headers={"X-Message-Id": f"stub-msg-{datetime.utcnow().timestamp()}"},
    )


# OpenAI endpoints
class OpenAICompletion(BaseModel):
    model: str
    messages: List[Dict[str, str]]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 150


@app.post("/v1/chat/completions")
async def openai_completion(completion: OpenAICompletion, authorization: str = Header(None)):
    """Mock OpenAI chat completion"""
    if not USE_STUBS:
        raise HTTPException(status_code=503, detail="Stub server disabled")

    # Generate stub recommendations
    recommendations = [
        {
            "issue": "Slow page load time",
            "impact": "Users abandon sites that take over 3 seconds to load",
            "effort": "medium",
            "improvement": "Could reduce bounce rate by 20%",
        },
        {
            "issue": "Missing meta descriptions",
            "impact": "Lower click-through rates from search results",
            "effort": "easy",
            "improvement": "Could increase organic traffic by 15%",
        },
        {
            "issue": "Not mobile optimized",
            "impact": "60% of users browse on mobile devices",
            "effort": "hard",
            "improvement": "Could increase mobile conversions by 35%",
        },
    ]

    return {
        "id": f"chatcmpl-stub-{datetime.utcnow().timestamp()}",
        "object": "chat.completion",
        "created": int(datetime.utcnow().timestamp()),
        "model": completion.model,
        "usage": {"prompt_tokens": 100, "completion_tokens": 150, "total_tokens": 250},
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": json.dumps(recommendations[:3]),
                },
                "finish_reason": "stop",
                "index": 0,
            }
        ],
    }


# SEMrush endpoints
@app.get("/")
async def semrush_domain_overview(
    key: Optional[str] = None,
    type: Optional[str] = None,
    domain: Optional[str] = None,
    database: Optional[str] = None,
    display_limit: Optional[int] = None,
    export_columns: Optional[str] = None,
):
    """Mock SEMrush domain overview API"""
    if not USE_STUBS:
        raise HTTPException(status_code=503, detail="Stub server disabled")

    # Validate required parameters
    if not key or not domain:
        raise HTTPException(status_code=400, detail="Missing required parameters")

    # Simulate API key validation
    if key == "invalid-key":
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Generate realistic SEMrush data
    is_popular = random.random() > 0.3  # 70% of domains are "popular"

    if is_popular:
        organic_keywords = random.randint(500, 5000)
        organic_traffic = random.randint(10000, 100000)
        organic_cost = round(random.uniform(5000, 50000), 2)
        adwords_keywords = random.randint(50, 500)
        adwords_traffic = random.randint(1000, 10000)
        adwords_cost = round(random.uniform(1000, 10000), 2)
    else:
        organic_keywords = random.randint(10, 500)
        organic_traffic = random.randint(100, 10000)
        organic_cost = round(random.uniform(100, 5000), 2)
        adwords_keywords = random.randint(0, 50)
        adwords_traffic = random.randint(0, 1000)
        adwords_cost = round(random.uniform(0, 1000), 2)

    # Return CSV format response as SEMrush does
    csv_response = f"Or;Ot;Oc;Ad;At;Ac\n{organic_keywords};{organic_traffic};{organic_cost};{adwords_keywords};{adwords_traffic};{adwords_cost}"

    return Response(content=csv_response, media_type="text/plain")


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "use_stubs": USE_STUBS,
    }


# Webhook simulation endpoints
@app.post("/webhooks/stripe")
async def simulate_stripe_webhook(event_type: str, session_id: str):
    """Simulate Stripe webhook events"""
    event = {
        "id": f"evt_stub_{datetime.utcnow().timestamp()}",
        "type": event_type,
        "created": int(datetime.utcnow().timestamp()),
        "data": {
            "object": {
                "id": session_id,
                "payment_intent": f"pi_test_{datetime.utcnow().timestamp()}",
                "amount_total": 19900,
                "currency": "usd",
                "customer_email": "test@example.com",
                "metadata": {"business_id": "test-business-123"},
            }
        },
    }
    return event


@app.post("/webhooks/sendgrid")
async def simulate_sendgrid_webhook(events: List[Dict[str, Any]]):
    """Simulate SendGrid webhook events"""
    processed_events = []

    for event in events:
        processed_events.append(
            {
                "email": event.get("email", "test@example.com"),
                "event": event.get("event", "delivered"),
                "timestamp": int(datetime.utcnow().timestamp()),
                "sg_message_id": f"stub-msg-{datetime.utcnow().timestamp()}",
                "business_id": event.get("business_id", "test-123"),
            }
        )

    return {"events_processed": len(processed_events)}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5011)
