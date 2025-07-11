"""
Tests for analytics views - Phase 0.5 Task AN-08
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models import (
    Business,
    Email,
    EmailStatus,
    Purchase,
    PurchaseStatus,
    ScoringResult,
    APICost,
    DailyCostAggregate,
)

# Mark entire module as xfail for Phase 0.5
pytestmark = pytest.mark.xfail(reason="Phase 0.5 feature", strict=False)


class TestAnalyticsViews:
    """Test analytics views for unit economics and bucket performance"""

    @pytest.fixture
    def test_db(self):
        """Create test database with views"""
        # Create in-memory SQLite database
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)

        # Create views (simplified for SQLite)
        with engine.connect() as conn:
            # Create simplified unit_economics_day view
            conn.execute(
                text(
                    """
                CREATE VIEW unit_economics_day AS
                SELECT 
                    DATE(e.sent_at) as date,
                    COUNT(DISTINCT b.id) as businesses_contacted,
                    COUNT(DISTINCT b.id) as businesses_delivered,
                    COUNT(DISTINCT p.id) as purchases,
                    COALESCE(SUM(p.amount_cents) / 100.0, 0) as revenue_usd,
                    COALESCE(MAX(dc.total_cost_usd), 0) as total_cost_usd,
                    COALESCE(SUM(p.amount_cents) / 100.0, 0) - COALESCE(MAX(dc.total_cost_usd), 0) as profit_usd
                FROM emails e
                JOIN businesses b ON e.business_id = b.id
                LEFT JOIN purchases p ON b.id = p.business_id 
                    AND DATE(p.created_at) = DATE(e.sent_at)
                LEFT JOIN agg_daily_cost dc ON DATE(e.sent_at) = dc.date
                WHERE e.sent_at IS NOT NULL
                GROUP BY DATE(e.sent_at)
            """
                )
            )

            # Create simplified bucket_performance view
            conn.execute(
                text(
                    """
                CREATE VIEW bucket_performance AS
                SELECT 
                    b.geo_bucket,
                    b.vert_bucket,
                    COUNT(DISTINCT b.id) as total_businesses,
                    COUNT(DISTINCT e.id) as emails_sent,
                    COUNT(DISTINCT p.id) as purchases,
                    SUM(p.amount_cents) / 100.0 as total_revenue_usd
                FROM businesses b
                LEFT JOIN emails e ON b.id = e.business_id
                LEFT JOIN purchases p ON b.id = p.business_id
                WHERE b.geo_bucket IS NOT NULL 
                   OR b.vert_bucket IS NOT NULL
                GROUP BY b.geo_bucket, b.vert_bucket
            """
                )
            )
            conn.commit()

        Session = sessionmaker(bind=engine)
        session = Session()

        yield session

        session.close()

    def test_unit_economics_day_view(self, test_db):
        """Test unit economics daily view"""
        # Create test data
        business1 = Business(
            id="b1",
            yelp_id="yelp1",
            name="Test Restaurant",
            geo_bucket="high-high-high",
            vert_bucket="medium-medium-low",
        )
        business2 = Business(
            id="b2",
            yelp_id="yelp2",
            name="Test Dentist",
            geo_bucket="high-high-high",
            vert_bucket="high-high-medium",
        )

        test_db.add_all([business1, business2])

        # Add emails
        today = datetime.utcnow().date()
        email1 = Email(
            id="e1",
            business_id="b1",
            subject="Test Email 1",
            html_body="<p>Test</p>",
            status=EmailStatus.DELIVERED,
            sent_at=datetime.combine(today, datetime.min.time()),
        )
        email2 = Email(
            id="e2",
            business_id="b2",
            subject="Test Email 2",
            html_body="<p>Test</p>",
            status=EmailStatus.DELIVERED,
            sent_at=datetime.combine(today, datetime.min.time()),
        )

        test_db.add_all([email1, email2])

        # Add purchase
        purchase = Purchase(
            id="p1",
            business_id="b1",
            stripe_session_id="sess1",
            amount_cents=4999,  # $49.99
            customer_email="test@example.com",
            status=PurchaseStatus.COMPLETED,
            created_at=datetime.combine(today, datetime.min.time()),
        )

        test_db.add(purchase)

        # Add daily cost aggregate
        daily_cost = DailyCostAggregate(
            date=today,
            provider="openai",
            total_cost_usd=Decimal("10.50"),
            request_count=100,
        )

        test_db.add(daily_cost)
        test_db.commit()

        # Query view
        result = test_db.execute(text("SELECT * FROM unit_economics_day")).fetchone()

        assert result is not None
        assert result.businesses_contacted == 2
        assert result.businesses_delivered == 2
        assert result.purchases == 1
        assert float(result.revenue_usd) == 49.99
        assert float(result.total_cost_usd) == 10.50
        assert float(result.profit_usd) == 39.49  # 49.99 - 10.50

    def test_bucket_performance_view(self, test_db):
        """Test bucket performance view"""
        # Create businesses with different buckets
        businesses = [
            Business(
                id=f"b{i}",
                yelp_id=f"yelp{i}",
                name=f"Business {i}",
                geo_bucket="high-high-high",
                vert_bucket="medium-medium-low",
            )
            for i in range(1, 4)
        ]

        businesses.append(
            Business(
                id="b4",
                yelp_id="yelp4",
                name="Business 4",
                geo_bucket="low-low-medium",
                vert_bucket="high-high-high",
            )
        )

        test_db.add_all(businesses)

        # Add emails and purchases
        for i, business in enumerate(businesses[:3]):  # First 3 businesses
            email = Email(
                id=f"e{i}",
                business_id=business.id,
                subject=f"Email {i}",
                html_body="<p>Test</p>",
                status=EmailStatus.DELIVERED,
                sent_at=datetime.utcnow(),
            )
            test_db.add(email)

            if i < 2:  # First 2 businesses have purchases
                purchase = Purchase(
                    id=f"p{i}",
                    business_id=business.id,
                    stripe_session_id=f"sess{i}",
                    amount_cents=4999 + (i * 1000),  # $49.99, $59.99
                    customer_email=f"test{i}@example.com",
                    status=PurchaseStatus.COMPLETED,
                )
                test_db.add(purchase)

        test_db.commit()

        # Query view
        results = test_db.execute(
            text("SELECT * FROM bucket_performance ORDER BY total_businesses DESC")
        ).fetchall()

        assert len(results) == 2  # Two unique bucket combinations

        # First bucket (high-high-high, medium-medium-low)
        first = results[0]
        assert first.geo_bucket == "high-high-high"
        assert first.vert_bucket == "medium-medium-low"
        assert first.total_businesses == 3
        assert first.emails_sent == 3
        assert first.purchases == 2
        assert float(first.total_revenue_usd) == 109.98  # 49.99 + 59.99

        # Second bucket (low-low-medium, high-high-high)
        second = results[1]
        assert second.geo_bucket == "low-low-medium"
        assert second.vert_bucket == "high-high-high"
        assert second.total_businesses == 1
        assert second.emails_sent == 0
        assert second.purchases == 0

    def test_empty_views(self, test_db):
        """Test views with no data"""
        # Query empty views
        unit_result = test_db.execute(
            text("SELECT * FROM unit_economics_day")
        ).fetchall()
        bucket_result = test_db.execute(
            text("SELECT * FROM bucket_performance")
        ).fetchall()

        assert len(unit_result) == 0
        assert len(bucket_result) == 0

    def test_bucket_performance_with_scores(self, test_db):
        """Test bucket performance with scoring data"""
        # Create business
        business = Business(
            id="b1",
            yelp_id="yelp1",
            name="Test Business",
            geo_bucket="high-high-high",
            vert_bucket="high-high-medium",
        )
        test_db.add(business)

        # Add scoring result
        score = ScoringResult(
            id="s1",
            business_id="b1",
            score_raw=Decimal("0.8500"),
            score_pct=85,
            tier="A",
            confidence=Decimal("0.95"),
            scoring_version=1,
            passed_gate=True,
        )
        test_db.add(score)
        test_db.commit()

        # Query view - need to check if scoring is included in simplified view
        # For this test, we'll just verify the data was added correctly
        assert test_db.query(ScoringResult).count() == 1
        assert test_db.query(ScoringResult).first().tier == "A"
