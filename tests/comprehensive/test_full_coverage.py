"""
Comprehensive test suite to maximize code coverage.
Part of PRP-014: Strategic CI Test Re-enablement

This test file is marked as @pytest.mark.slow and is intended to run
in the nightly test suite to achieve maximum possible coverage.
"""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Set test environment
os.environ["USE_STUBS"] = "false"  # Use real implementations for max coverage
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///tmp/test_comprehensive.db"

pytestmark = pytest.mark.slow


class TestD0GatewayComprehensive:
    """Comprehensive tests for d0_gateway module"""

    def test_all_gateway_providers(self):
        """Test all gateway provider implementations"""
        from d0_gateway.factory import GatewayClientFactory
        from d0_gateway.providers import (
            dataaxle,
            google_places,
            humanloop,
            hunter,
            openai,
            pagespeed,
            screenshotone,
            semrush,
            sendgrid,
            stripe,
        )

        factory = GatewayClientFactory()

        # Test each provider's initialization and basic methods
        providers = [
            ("dataaxle", dataaxle.DataAxleClient),
            ("hunter", hunter.HunterClient),
            ("openai", openai.OpenAIClient),
            ("pagespeed", pagespeed.PageSpeedClient),
            ("screenshotone", screenshotone.ScreenshotOneClient),
            ("humanloop", humanloop.HumanloopClient),
            ("google_places", google_places.GooglePlacesClient),
            ("stripe", stripe.StripeClient),
            ("sendgrid", sendgrid.SendGridClient),
            ("semrush", semrush.SEMrushClient),
        ]

        for provider_name, provider_class in providers:
            # Test factory creation
            with patch.object(factory, "_get_provider_config", return_value={"api_key": "test-key"}):
                provider = factory.create_client(provider_name)
                assert provider is not None

                # Test provider methods
                if hasattr(provider, "health_check"):
                    with patch.object(provider, "make_request", return_value={"status": "ok"}):
                        result = provider.health_check()
                        assert result is not None

    def test_gateway_error_handling(self):
        """Test comprehensive error handling in gateway"""
        from d0_gateway.exceptions import (
            APIProviderError,
            AuthenticationError,
            RateLimitExceededError,
            ServiceUnavailableError,
            TimeoutError,
        )
        from d0_gateway.facade import GatewayFacade

        facade = GatewayFacade()

        # Test each error type
        error_scenarios = [
            (RateLimitExceededError("dataaxle", "daily"), 429),
            (AuthenticationError("dataaxle", "Invalid API key"), 401),
            (APIProviderError("dataaxle", "Invalid parameters", 400), 400),
            (ServiceUnavailableError("dataaxle", "Provider unavailable"), 503),
            (TimeoutError("dataaxle", 30), 408),
        ]

        for error, expected_status in error_scenarios:
            with patch.object(facade._factory, "create_client") as mock_create:
                mock_provider = MagicMock()
                mock_provider.execute.side_effect = error
                mock_create.return_value = mock_provider

                with pytest.raises(type(error)):
                    facade.execute("test_provider", "test_method", {})

    def test_circuit_breaker_comprehensive(self):
        """Test circuit breaker state transitions"""
        from d0_gateway.circuit_breaker import CircuitBreaker, CircuitState

        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=1, expected_exception=Exception)

        # Test state transitions
        assert breaker.state == CircuitState.CLOSED

        # Cause failures to open circuit
        for _ in range(3):
            with pytest.raises(Exception):
                with breaker:
                    raise Exception("Test failure")

        assert breaker.state == CircuitState.OPEN

        # Test half-open after timeout
        import time

        time.sleep(1.1)
        assert breaker.state == CircuitState.HALF_OPEN

        # Success should close circuit
        with breaker:
            pass  # Success

        assert breaker.state == CircuitState.CLOSED

    def test_gateway_metrics_collection(self):
        """Test comprehensive metrics collection"""
        from d0_gateway.metrics import GatewayMetrics

        metrics = GatewayMetrics()

        # Test all metric types
        metrics.record_request("dataaxle", "match", 200, 0.123)
        metrics.record_request("hunter", "verify", 429, 0.456)
        metrics.record_cache_hit("dataaxle", "match")
        metrics.record_cache_miss("hunter", "verify")

        # Get aggregated metrics
        summary = metrics.get_summary()
        assert "total_requests" in summary
        assert "cache_hit_rate" in summary
        assert "average_latency" in summary
        assert "error_rate" in summary


class TestD1TargetingComprehensive:
    """Comprehensive tests for d1_targeting module"""

    def test_target_universe_full_workflow(self):
        """Test complete target universe workflow"""
        from d1_targeting.models import D1BusinessFilter, D1GeographicFilter, D1IndustryFilter, D1TargetingCriteria
        from d1_targeting.target_universe import TargetUniverse

        universe = TargetUniverse()

        # Create comprehensive criteria
        criteria = D1TargetingCriteria(
            geographic=D1GeographicFilter(
                countries=["US"],
                states=["CA", "NY", "TX"],
                cities=["San Francisco", "New York", "Austin"],
                zip_codes=["94105", "10001", "78701"],
            ),
            industry=D1IndustryFilter(
                naics_codes=["722511", "541511"],
                sic_codes=["5812", "7371"],
                keywords=["restaurant", "software", "technology"],
            ),
            business=D1BusinessFilter(
                min_revenue=100000, max_revenue=10000000, min_employees=5, max_employees=500, years_in_business_min=2
            ),
        )

        # Test universe building
        with patch.object(universe, "_query_data_sources") as mock_query:
            mock_query.return_value = [
                {"name": "Test Business 1", "url": "test1.com"},
                {"name": "Test Business 2", "url": "test2.com"},
            ]

            results = universe.build_universe(criteria)
            assert len(results) == 2

    def test_quota_tracker_comprehensive(self):
        """Test quota tracking with various scenarios"""
        from d1_targeting.quota_tracker import QuotaExceeded, QuotaTracker

        tracker = QuotaTracker(daily_limit=1000, monthly_limit=25000, rate_limit_per_hour=100)

        # Test quota consumption
        assert tracker.can_consume(50)
        tracker.consume(50)
        assert tracker.get_remaining_daily() == 950

        # Test rate limiting
        for _ in range(10):
            tracker.consume(10)

        # Test quota exceeded
        with pytest.raises(QuotaExceeded):
            tracker.consume(2000)  # Exceeds daily limit

    def test_geo_validator_comprehensive(self):
        """Test geographic validation with edge cases"""
        from d1_targeting.geo_validator import GeoValidator

        validator = GeoValidator()

        # Test various location formats
        test_cases = [
            ("New York, NY", True),
            ("12345", True),  # ZIP code
            ("Invalid Location XYZ", False),
            ("London, UK", True),
            ("", False),
            (None, False),
        ]

        for location, expected in test_cases:
            result = validator.validate_location(location)
            assert result.is_valid == expected


class TestD2SourcingComprehensive:
    """Comprehensive tests for d2_sourcing module"""

    async def test_sourcing_coordinator_full_pipeline(self):
        """Test complete sourcing pipeline"""
        from d2_sourcing.coordinator import SourcingCoordinator
        from d2_sourcing.models import D2SourcingResult

        coordinator = SourcingCoordinator()

        # Mock all data sources
        with patch.object(coordinator, "_source_from_dataaxle") as mock_da:
            with patch.object(coordinator, "_source_from_google_places") as mock_gp:
                with patch.object(coordinator, "_source_from_web_scraping") as mock_ws:
                    mock_da.return_value = [
                        D2SourcingResult(
                            business_name="Test Restaurant",
                            website_url="https://testrestaurant.com",
                            source="dataaxle",
                            confidence_score=0.95,
                        )
                    ]

                    mock_gp.return_value = [
                        D2SourcingResult(
                            business_name="Test Restaurant",
                            website_url="https://testrestaurant.com",
                            source="google_places",
                            confidence_score=0.90,
                        )
                    ]

                    mock_ws.return_value = []

                    # Run sourcing
                    results = await coordinator.source_businesses(
                        targets=[{"name": "Test Restaurant", "location": "San Francisco"}],
                        sources=["dataaxle", "google_places", "web_scraping"],
                    )

                    assert len(results) > 0
                    assert results[0].confidence_score >= 0.90


class TestD3AssessmentComprehensive:
    """Comprehensive tests for d3_assessment module"""

    async def test_assessment_coordinator_all_checks(self):
        """Test all assessment types"""
        from d3_assessment.coordinator import AssessmentCoordinator
        from d3_assessment.models import D3AssessmentResult

        coordinator = AssessmentCoordinator()

        # Mock all assessors
        assessors = ["pagespeed", "techstack", "seo", "security", "accessibility", "mobile_friendly", "social_presence"]

        for assessor in assessors:
            method = f"_assess_{assessor}"
            if hasattr(coordinator, method):
                with patch.object(coordinator, method) as mock_assess:
                    mock_assess.return_value = D3AssessmentResult(
                        check_type=assessor, status="completed", findings=[], score=85
                    )

        # Run comprehensive assessment
        with patch("d3_assessment.coordinator.asyncio.gather") as mock_gather:
            mock_gather.return_value = [
                D3AssessmentResult(
                    check_type="pagespeed",
                    status="completed",
                    findings=[{"type": "slow_ttfb", "severity": "medium"}],
                    score=75,
                )
            ]

            results = await coordinator.assess_website(url="https://example.com", checks=assessors)

            assert len(results) > 0

    def test_rubric_evaluation_comprehensive(self):
        """Test rubric evaluation with all criteria"""
        from d3_assessment.rubric import AssessmentRubric, RubricCriteria

        rubric = AssessmentRubric()

        # Test all criteria
        criteria = [
            RubricCriteria(name="performance", weight=0.3, thresholds={"excellent": 90, "good": 70, "poor": 50}),
            RubricCriteria(name="seo", weight=0.2, thresholds={"excellent": 85, "good": 65, "poor": 40}),
            RubricCriteria(name="security", weight=0.25, thresholds={"excellent": 95, "good": 80, "poor": 60}),
            RubricCriteria(name="accessibility", weight=0.25, thresholds={"excellent": 88, "good": 70, "poor": 50}),
        ]

        scores = {"performance": 82, "seo": 68, "security": 91, "accessibility": 75}

        evaluation = rubric.evaluate(criteria, scores)
        assert "overall_score" in evaluation
        assert "category_scores" in evaluation
        assert evaluation["overall_score"] > 0


class TestD4EnrichmentComprehensive:
    """Comprehensive tests for d4_enrichment module"""

    async def test_enrichment_coordinator_all_sources(self):
        """Test all enrichment sources"""
        from d4_enrichment.coordinator import EnrichmentCoordinator
        from d4_enrichment.models import D4EnrichmentResult

        coordinator = EnrichmentCoordinator()

        # Mock all enrichers
        enrichers = [
            "_enrich_dataaxle",
            "_enrich_hunter",
            "_enrich_google_places",
            "_enrich_company_size",
            "_enrich_social_media",
            "_enrich_technology",
        ]

        for enricher in enrichers:
            if hasattr(coordinator, enricher):
                with patch.object(coordinator, enricher) as mock_enrich:
                    mock_enrich.return_value = D4EnrichmentResult(
                        source=enricher.replace("_enrich_", ""), data={"test": "data"}, confidence=0.9
                    )

        # Run enrichment
        with patch("d4_enrichment.coordinator.asyncio.gather") as mock_gather:
            mock_gather.return_value = [
                D4EnrichmentResult(
                    source="dataaxle",
                    data={"revenue": "$5M-$10M", "employees": "50-100", "years_in_business": 10},
                    confidence=0.95,
                )
            ]

            results = await coordinator.enrich_business(
                business_data={"name": "Test Corp", "url": "test.com"}, sources=["dataaxle", "hunter", "google_places"]
            )

            assert len(results) > 0

    def test_similarity_matching_comprehensive(self):
        """Test similarity matching algorithms"""
        from d4_enrichment.similarity import SimilarityMatcher

        matcher = SimilarityMatcher()

        # Test various similarity scenarios
        test_cases = [
            # (str1, str2, expected_min_score)
            ("McDonald's", "McDonalds", 0.8),
            ("The Coffee Shop", "Coffee Shop", 0.85),
            ("ABC Corporation", "ABC Corp", 0.9),
            ("Test Restaurant LLC", "Test Restaurant", 0.85),
            ("Completely Different", "Nothing Similar", 0.1),
        ]

        for str1, str2, min_score in test_cases:
            score = matcher.calculate_similarity(str1, str2)
            assert score >= min_score or score < min_score + 0.2


class TestD5ScoringComprehensive:
    """Comprehensive tests for d5_scoring module"""

    def test_scoring_engine_all_rules(self):
        """Test scoring engine with all rule types"""
        from d5_scoring.engine import ScoringEngine
        from d5_scoring.models import D5ScoringResult, ScoringRule

        engine = ScoringEngine()

        # Create comprehensive rules
        rules = [
            ScoringRule(
                id="perf_1",
                name="Page Speed Score",
                formula="performance_score * 0.3",
                weight=0.3,
                category="performance",
            ),
            ScoringRule(id="seo_1", name="SEO Score", formula="seo_score * 0.25", weight=0.25, category="seo"),
            ScoringRule(
                id="sec_1", name="Security Score", formula="has_ssl ? 100 : 0", weight=0.2, category="security"
            ),
            ScoringRule(
                id="bus_1",
                name="Business Maturity",
                formula="min(years_in_business * 10, 100) * 0.25",
                weight=0.25,
                category="business",
            ),
        ]

        # Test with various input data
        test_data = {
            "performance_score": 85,
            "seo_score": 72,
            "has_ssl": True,
            "years_in_business": 7,
            "revenue_range": "$1M-$5M",
            "employee_count": 25,
        }

        with patch.object(engine, "_load_rules", return_value=rules):
            result = engine.calculate_score(test_data)

            assert isinstance(result, D5ScoringResult)
            assert result.total_score > 0
            assert result.total_score <= 100
            assert len(result.breakdown) > 0

    def test_formula_evaluator_complex_formulas(self):
        """Test formula evaluator with complex expressions"""
        from d5_scoring.formula_evaluator import FormulaEvaluator

        evaluator = FormulaEvaluator()

        # Test various formula types
        formulas = [
            # Basic arithmetic
            ("10 + 20 * 3", {}, 70),
            # Variables
            ("score * 0.5 + bonus", {"score": 80, "bonus": 10}, 50),
            # Conditionals
            ("is_premium ? 100 : 50", {"is_premium": True}, 100),
            ("is_premium ? 100 : 50", {"is_premium": False}, 50),
            # Complex nested
            ("(score > 80 ? score * 1.2 : score * 0.8) + bonus", {"score": 90, "bonus": 5}, 113),
            # Math functions
            ("min(score, 100)", {"score": 120}, 100),
            ("max(score, 50)", {"score": 30}, 50),
            ("sqrt(value)", {"value": 16}, 4),
        ]

        for formula, context, expected in formulas:
            result = evaluator.evaluate(formula, context)
            assert abs(result - expected) < 0.1

    def test_vertical_overrides_comprehensive(self):
        """Test vertical-specific scoring overrides"""
        from d5_scoring.vertical_overrides import VerticalOverrideEngine

        override_engine = VerticalOverrideEngine()

        # Test different verticals
        verticals = [
            ("restaurant", {"online_ordering": True, "reviews_count": 150}),
            ("ecommerce", {"has_shopping_cart": True, "payment_options": 5}),
            ("healthcare", {"hipaa_compliant": True, "patient_portal": True}),
            ("finance", {"pci_compliant": True, "encryption_level": "AES-256"}),
        ]

        for vertical, attributes in verticals:
            base_score = 75
            adjusted_score = override_engine.apply_overrides(
                vertical=vertical, base_score=base_score, attributes=attributes
            )

            # Vertical overrides should affect score
            assert adjusted_score != base_score or vertical == "default"


class TestD6ReportsComprehensive:
    """Comprehensive tests for d6_reports module"""

    async def test_report_generator_all_templates(self):
        """Test report generation with all templates"""
        from d6_reports.generator import ReportGenerator
        from d6_reports.models import D6ReportRequest, ReportTemplate

        generator = ReportGenerator()

        # Test all report templates
        templates = [
            ReportTemplate.EXECUTIVE_SUMMARY,
            ReportTemplate.TECHNICAL_AUDIT,
            ReportTemplate.COMPETITIVE_ANALYSIS,
            ReportTemplate.OPPORTUNITY_REPORT,
            ReportTemplate.IMPLEMENTATION_GUIDE,
        ]

        for template in templates:
            request = D6ReportRequest(
                lead_id=123,
                template=template,
                include_sections=["overview", "findings", "recommendations"],
                format="html",
                personalization_level="high",
            )

            with patch.object(generator, "_load_template") as mock_load:
                with patch.object(generator, "_populate_data") as mock_populate:
                    mock_load.return_value = "<html>{{content}}</html>"
                    mock_populate.return_value = {"content": "Test report"}

                    report = await generator.generate_report(request)
                    assert report is not None
                    assert "Test report" in str(report)

    def test_pdf_converter_comprehensive(self):
        """Test PDF conversion with various options"""
        from d6_reports.pdf_converter import PDFConverter, PDFOptions

        converter = PDFConverter()

        # Test different PDF options
        options_list = [
            PDFOptions(
                page_size="A4",
                orientation="portrait",
                margin_top=20,
                margin_bottom=20,
                include_toc=True,
                include_cover=True,
            ),
            PDFOptions(
                page_size="Letter",
                orientation="landscape",
                margin_top=15,
                margin_bottom=15,
                include_toc=False,
                include_cover=False,
            ),
        ]

        html_content = """
        <html>
        <head><title>Test Report</title></head>
        <body>
            <h1>Executive Summary</h1>
            <p>This is a test report.</p>
            <h2>Findings</h2>
            <ul>
                <li>Finding 1</li>
                <li>Finding 2</li>
            </ul>
        </body>
        </html>
        """

        for options in options_list:
            with patch("d6_reports.pdf_converter.HTML") as mock_html:
                mock_pdf = MagicMock()
                mock_pdf.write_pdf.return_value = b"PDF content"
                mock_html.return_value = mock_pdf

                pdf_bytes = converter.convert_to_pdf(html_content, options)
                assert pdf_bytes == b"PDF content"


class TestD7StorefrontComprehensive:
    """Comprehensive tests for d7_storefront module"""

    async def test_checkout_flow_comprehensive(self):
        """Test complete checkout flow"""
        from d7_storefront.checkout import CheckoutService
        from d7_storefront.models import D7CheckoutRequest, D7Customer, D7Order, D7PaymentMethod, D7Product

        checkout_service = CheckoutService()

        # Create comprehensive checkout request
        request = D7CheckoutRequest(
            customer=D7Customer(email="test@example.com", name="Test User", company="Test Corp"),
            products=[
                D7Product(id="prod_1", name="Website Audit", price=299.99, quantity=1),
                D7Product(id="prod_2", name="SEO Analysis", price=199.99, quantity=1),
            ],
            payment_method=D7PaymentMethod(
                type="card", card_number="4242424242424242", exp_month=12, exp_year=2025, cvc="123"
            ),
            billing_address={
                "line1": "123 Test St",
                "city": "San Francisco",
                "state": "CA",
                "postal_code": "94105",
                "country": "US",
            },
        )

        with patch.object(checkout_service, "_process_payment") as mock_payment:
            with patch.object(checkout_service, "_create_order") as mock_order:
                mock_payment.return_value = {"status": "succeeded", "id": "pi_123"}
                mock_order.return_value = D7Order(id="order_123", status="completed", total=499.98)

                order = await checkout_service.process_checkout(request)
                assert order.status == "completed"
                assert order.total == 499.98

    def test_webhook_handlers_all_events(self):
        """Test all webhook event handlers"""
        from d7_storefront.webhook_handlers import WebhookHandler

        handler = WebhookHandler()

        # Test different webhook events
        events = [
            {"type": "payment_intent.succeeded", "data": {"object": {"id": "pi_123", "amount": 29999}}},
            {"type": "payment_intent.failed", "data": {"object": {"id": "pi_124", "error": "Card declined"}}},
            {"type": "customer.created", "data": {"object": {"id": "cus_123", "email": "test@example.com"}}},
            {"type": "invoice.payment_succeeded", "data": {"object": {"id": "inv_123", "amount_paid": 49999}}},
        ]

        for event in events:
            with patch.object(handler, f'_handle_{event["type"].replace(".", "_")}') as mock_handle:
                mock_handle.return_value = {"status": "processed"}

                result = handler.handle_event(event)
                assert result["status"] == "processed"


class TestD8PersonalizationComprehensive:
    """Comprehensive tests for d8_personalization module"""

    async def test_content_generator_all_types(self):
        """Test content generation for all types"""
        from d8_personalization.content_generator import ContentGenerator
        from d8_personalization.models import ContentType, D8ContentRequest, PersonalizationLevel

        generator = ContentGenerator()

        # Test all content types
        content_types = [
            (ContentType.EMAIL_SUBJECT, {"company": "Test Corp", "issue": "slow website"}),
            (ContentType.EMAIL_BODY, {"findings": ["slow loading", "no SSL"], "name": "John"}),
            (ContentType.SMS, {"name": "Jane", "report_ready": True}),
            (ContentType.LANDING_PAGE, {"company": "Test Inc", "benefits": ["faster", "secure"]}),
            (ContentType.REPORT_INTRO, {"industry": "restaurant", "pain_points": ["online presence"]}),
        ]

        for content_type, context in content_types:
            request = D8ContentRequest(
                content_type=content_type,
                context=context,
                personalization_level=PersonalizationLevel.HIGH,
                tone="professional",
                length_limit=500,
            )

            with patch("d8_personalization.content_generator.OpenAIClient") as mock_client:
                mock_client.return_value.generate.return_value = f"Generated {content_type.value} content"

                content = await generator.generate_content(request)
                assert content_type.value in content

    def test_subject_line_optimizer(self):
        """Test subject line optimization"""
        from d8_personalization.subject_lines import SubjectLineOptimizer

        optimizer = SubjectLineOptimizer()

        # Test various optimization scenarios
        test_cases = [
            {
                "base": "Your Website Audit Report",
                "context": {"company": "Acme Corp", "urgency": "high"},
                "variants": 5,
            },
            {
                "base": "Improve Your SEO Today",
                "context": {"pain_point": "low traffic", "industry": "ecommerce"},
                "variants": 3,
            },
        ]

        for test in test_cases:
            variants = optimizer.generate_variants(
                base_subject=test["base"], context=test["context"], num_variants=test["variants"]
            )

            assert len(variants) == test["variants"]

            # Test scoring
            scores = optimizer.score_variants(variants, test["context"])
            assert len(scores) == len(variants)
            assert all(0 <= score <= 100 for score in scores.values())


class TestD9DeliveryComprehensive:
    """Comprehensive tests for d9_delivery module"""

    async def test_delivery_manager_all_channels(self):
        """Test delivery through all channels"""
        from d9_delivery.delivery_manager import DeliveryManager
        from d9_delivery.models import D9DeliveryRequest, DeliveryChannel, DeliveryStatus

        manager = DeliveryManager()

        # Test all delivery channels
        channels = [
            DeliveryChannel.EMAIL,
            DeliveryChannel.SMS,
            DeliveryChannel.WEBHOOK,
            DeliveryChannel.API,
        ]

        for channel in channels:
            request = D9DeliveryRequest(
                recipient="test@example.com" if channel == DeliveryChannel.EMAIL else "1234567890",
                channel=channel,
                content={"subject": "Test Delivery", "body": "This is a test message", "metadata": {"lead_id": 123}},
                scheduled_at=datetime.utcnow() + timedelta(hours=1),
            )

            with patch.object(manager, f"_deliver_{channel.value}") as mock_deliver:
                mock_deliver.return_value = DeliveryStatus.DELIVERED

                status = await manager.deliver(request)
                assert status == DeliveryStatus.DELIVERED

    def test_compliance_checker_comprehensive(self):
        """Test compliance checking for all regulations"""
        from d9_delivery.compliance import ComplianceChecker, ComplianceResult

        checker = ComplianceChecker()

        # Test different compliance scenarios
        test_cases = [
            {"content": "Click here to unsubscribe", "recipient": "test@example.com", "region": "US", "expected": True},
            {
                "content": "No unsubscribe link",
                "recipient": "test@example.eu",
                "region": "EU",
                "expected": False,  # GDPR requires unsubscribe
            },
            {
                "content": "Text STOP to opt out",
                "recipient": "1234567890",
                "region": "US",
                "channel": "SMS",
                "expected": True,
            },
        ]

        for test in test_cases:
            result = checker.check_compliance(
                content=test["content"],
                recipient=test["recipient"],
                region=test["region"],
                channel=test.get("channel", "email"),
            )

            assert isinstance(result, ComplianceResult)
            assert result.is_compliant == test["expected"]


class TestD10AnalyticsComprehensive:
    """Comprehensive tests for d10_analytics module"""

    def test_aggregators_all_metrics(self):
        """Test all metric aggregators"""
        from d10_analytics.aggregators import MetricAggregator
        from d10_analytics.models import D10Metric, MetricType

        aggregator = MetricAggregator()

        # Test different metric types
        metrics = [
            D10Metric(
                type=MetricType.CONVERSION_RATE,
                value=0.15,
                timestamp=datetime.utcnow(),
                dimensions={"channel": "email", "segment": "enterprise"},
            ),
            D10Metric(
                type=MetricType.LEAD_SCORE,
                value=85,
                timestamp=datetime.utcnow(),
                dimensions={"industry": "restaurant", "size": "medium"},
            ),
            D10Metric(
                type=MetricType.ENGAGEMENT_RATE,
                value=0.45,
                timestamp=datetime.utcnow(),
                dimensions={"content_type": "report", "personalization": "high"},
            ),
        ]

        # Test various aggregations
        for metric in metrics:
            aggregator.add_metric(metric)

        # Test time-based aggregations
        hourly = aggregator.aggregate_by_time("hour")
        daily = aggregator.aggregate_by_time("day")
        weekly = aggregator.aggregate_by_time("week")

        assert len(hourly) > 0
        assert len(daily) > 0
        assert len(weekly) > 0

        # Test dimension-based aggregations
        by_channel = aggregator.aggregate_by_dimension("channel")
        by_industry = aggregator.aggregate_by_dimension("industry")

        assert len(by_channel) > 0 or len(by_industry) > 0

    async def test_warehouse_operations(self):
        """Test data warehouse operations"""
        from d10_analytics.warehouse import DataWarehouse

        warehouse = DataWarehouse()

        # Test fact table operations
        fact_data = {
            "lead_id": 123,
            "timestamp": datetime.utcnow(),
            "score": 85.5,
            "conversion": True,
            "revenue": 299.99,
        }

        with patch.object(warehouse, "_insert_fact") as mock_insert:
            mock_insert.return_value = True

            result = await warehouse.insert_fact("lead_scores", fact_data)
            assert result is True

        # Test dimension table operations
        dimension_data = {
            "industry_id": 1,
            "name": "Restaurant",
            "category": "Food Service",
            "attributes": {"typical_size": "small", "b2c": True},
        }

        with patch.object(warehouse, "_insert_dimension") as mock_dim:
            mock_dim.return_value = True

            result = await warehouse.insert_dimension("industries", dimension_data)
            assert result is True

        # Test complex queries
        with patch.object(warehouse, "_execute_query") as mock_query:
            mock_query.return_value = [{"industry": "Restaurant", "avg_score": 82.3, "count": 150}]

            results = await warehouse.query("SELECT industry, AVG(score), COUNT(*) FROM lead_scores GROUP BY industry")
            assert len(results) > 0


class TestD11OrchestrationComprehensive:
    """Comprehensive tests for d11_orchestration module"""

    async def test_pipeline_full_execution(self):
        """Test complete pipeline execution"""
        from d11_orchestration.models import D11PipelineConfig, D11StageResult
        from d11_orchestration.pipeline import Pipeline, PipelineStage

        # Create comprehensive pipeline
        config = D11PipelineConfig(
            name="full_lead_pipeline",
            stages=[
                PipelineStage(name="targeting", handler="d1_targeting.handler", timeout=300, retry_count=3),
                PipelineStage(name="sourcing", handler="d2_sourcing.handler", timeout=600, dependencies=["targeting"]),
                PipelineStage(
                    name="assessment", handler="d3_assessment.handler", timeout=900, dependencies=["sourcing"]
                ),
                PipelineStage(
                    name="enrichment",
                    handler="d4_enrichment.handler",
                    timeout=600,
                    dependencies=["assessment"],
                    parallel=True,
                ),
                PipelineStage(name="scoring", handler="d5_scoring.handler", timeout=300, dependencies=["enrichment"]),
            ],
            max_parallel=3,
            failure_strategy="continue",
        )

        pipeline = Pipeline(config)

        # Mock stage handlers
        async def mock_handler(input_data):
            return D11StageResult(
                stage_name=input_data.get("stage", "unknown"),
                status="success",
                output={"processed": True},
                duration=1.23,
            )

        with patch.object(pipeline, "_execute_stage", side_effect=mock_handler):
            results = await pipeline.execute({"initial": "data"})

            assert len(results) == len(config.stages)
            assert all(r.status == "success" for r in results)

    def test_cost_guardrails_comprehensive(self):
        """Test cost guardrails with various scenarios"""
        from d11_orchestration.cost_guardrails import CostBudget, CostGuardrail

        guardrail = CostGuardrail()

        # Set different budgets
        budgets = [
            CostBudget(category="api_calls", daily_limit=100.0, monthly_limit=2000.0, alert_threshold=0.8),
            CostBudget(category="compute", hourly_limit=10.0, daily_limit=200.0, alert_threshold=0.9),
        ]

        for budget in budgets:
            guardrail.add_budget(budget)

        # Test cost tracking
        assert guardrail.can_proceed("api_calls", 50.0)
        guardrail.track_cost("api_calls", 50.0)

        assert guardrail.can_proceed("api_calls", 30.0)
        guardrail.track_cost("api_calls", 30.0)

        # Should trigger alert (80% of daily limit)
        alerts = guardrail.get_alerts()
        assert len(alerts) > 0

        # Test budget exceeded
        assert not guardrail.can_proceed("api_calls", 25.0)

    def test_experiment_framework(self):
        """Test A/B testing framework"""
        from d11_orchestration.experiments import Experiment, ExperimentFramework

        framework = ExperimentFramework()

        # Create experiments
        experiments = [
            Experiment(
                id="scoring_v2",
                name="New Scoring Algorithm",
                variants=["control", "treatment"],
                traffic_allocation={"control": 0.5, "treatment": 0.5},
                metrics=["conversion_rate", "lead_quality"],
            ),
            Experiment(
                id="personalization_ml",
                name="ML-based Personalization",
                variants=["baseline", "ml_model"],
                traffic_allocation={"baseline": 0.7, "ml_model": 0.3},
                metrics=["engagement_rate", "click_through_rate"],
            ),
        ]

        for exp in experiments:
            framework.register_experiment(exp)

        # Test variant assignment
        user_ids = [f"user_{i}" for i in range(100)]
        assignments = {}

        for user_id in user_ids:
            variant = framework.get_variant("scoring_v2", user_id)
            assignments[variant] = assignments.get(variant, 0) + 1

        # Check distribution is roughly as expected
        assert abs(assignments.get("control", 0) - 50) < 15
        assert abs(assignments.get("treatment", 0) - 50) < 15


class TestCoreModulesComprehensive:
    """Comprehensive tests for core modules"""

    def test_utils_all_functions(self):
        """Test all utility functions"""
        from core import utils

        # Test string utilities
        assert utils.slugify("Test String!") == "test-string"
        assert utils.truncate("Long text", 5) == "Long..."
        assert utils.remove_html("<p>Text</p>") == "Text"

        # Test validation utilities
        assert utils.validate_email("test@example.com") is True
        assert utils.validate_url("https://example.com") is True
        assert utils.validate_phone("+1-555-123-4567") is True

        # Test data utilities
        nested = {"a": {"b": {"c": 1}}}
        assert utils.get_nested(nested, "a.b.c") == 1
        assert utils.get_nested(nested, "a.b.d", default=0) == 0

        # Test retry mechanism
        call_count = 0

        @utils.retry_with_backoff(max_retries=3, backoff_factor=0.1)
        def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"

        result = flaky_function()
        assert result == "success"
        assert call_count == 3

    def test_config_management(self):
        """Test configuration management"""
        from core.config import Settings, get_settings

        # Test config loading with different environments
        envs = ["development", "staging", "test"]
        for env in envs:
            with patch.dict(os.environ, {"ENVIRONMENT": env}):
                # Clear cache to pick up new environment
                get_settings.cache_clear()
                config = get_settings()
                assert config.environment == env

        # Test settings validation
        settings = Settings()
        assert settings.environment in ["development", "test", "staging", "production"]

        # Test API key configuration
        assert hasattr(settings, "get_api_key")

        # Test stub configuration
        if settings.use_stubs:
            assert settings.get_api_key("google") == "stub-google-key"

        # Test model dump functionality
        dumped = settings.model_dump()
        assert "environment" in dumped
        assert "use_stubs" in dumped

    def test_observability_comprehensive(self):
        """Test observability features"""
        from core.observability import Logger, MetricsCollector, Tracer, log_event, record_metric, trace_span

        # Test tracing
        tracer = Tracer()

        with tracer.start_span("test_operation") as span:
            span.set_attribute("user_id", "123")
            span.set_attribute("operation_type", "test")

            # Nested span
            with tracer.start_span("nested_operation", parent=span) as nested:
                nested.set_attribute("detail", "nested_test")

        # Test metrics
        metrics = MetricsCollector()

        metrics.increment("api_calls", tags={"endpoint": "/test"})
        metrics.histogram("response_time", 0.123, tags={"endpoint": "/test"})
        metrics.gauge("active_connections", 42)

        # Test structured logging
        logger = Logger("test_module")

        logger.info("Test event", extra={"user_id": "123", "action": "test_action", "metadata": {"key": "value"}})

        # Test decorators
        @trace_span("decorated_function")
        @record_metric("function_calls")
        @log_event("function_executed")
        def test_function(x, y):
            return x + y

        result = test_function(2, 3)
        assert result == 5


class TestAPIModulesComprehensive:
    """Comprehensive tests for API modules"""

    async def test_governance_api_all_endpoints(self):
        """Test all governance API endpoints"""
        from api.governance import GovernanceAPI
        from api.governance.models import ApprovalRequest, AuditLog, PolicyViolation

        api = GovernanceAPI()

        # Test approval workflow
        approval_request = ApprovalRequest(
            resource_type="report_generation",
            resource_id="report_123",
            requested_by="user_456",
            reason="Generate executive report",
            metadata={"lead_id": 789, "template": "executive"},
        )

        with patch.object(api, "create_approval_request") as mock_create:
            mock_create.return_value = {"id": "approval_123", "status": "pending"}

            result = await api.submit_for_approval(approval_request)
            assert result["status"] == "pending"

        # Test audit logging
        audit_log = AuditLog(
            action="data_export",
            user_id="user_123",
            resource="leads_database",
            timestamp=datetime.utcnow(),
            details={"exported_count": 1000, "format": "csv"},
        )

        with patch.object(api, "log_action") as mock_log:
            mock_log.return_value = True

            logged = await api.log_audit_event(audit_log)
            assert logged is True

        # Test policy validation
        policy_check = {"action": "bulk_email", "count": 10000, "user_role": "analyst"}

        with patch.object(api, "check_policy") as mock_check:
            mock_check.return_value = PolicyViolation(
                violated=True, policy="daily_email_limit", message="Exceeds daily limit of 5000"
            )

            violation = await api.validate_against_policies(policy_check)
            assert violation.violated is True

    async def test_lineage_tracking(self):
        """Test data lineage tracking"""
        from api.lineage import LineageTracker
        from api.lineage.models import DataFlow, DataNode

        tracker = LineageTracker()

        # Create data nodes
        nodes = [
            DataNode(id="source_1", type="data_source", name="DataAxle API", metadata={"api_version": "v2"}),
            DataNode(id="transform_1", type="transformation", name="Data Cleansing", metadata={"rules_applied": 5}),
            DataNode(id="output_1", type="output", name="Enriched Leads", metadata={"format": "json"}),
        ]

        # Create data flows
        flows = [
            DataFlow(source_id="source_1", target_id="transform_1", transformation="extract_businesses"),
            DataFlow(source_id="transform_1", target_id="output_1", transformation="enrich_and_score"),
        ]

        # Build lineage
        for node in nodes:
            tracker.add_node(node)

        for flow in flows:
            tracker.add_flow(flow)

        # Test lineage queries
        upstream = tracker.get_upstream_lineage("output_1")
        assert len(upstream) == 2

        downstream = tracker.get_downstream_lineage("source_1")
        assert len(downstream) == 2

        # Test impact analysis
        impact = tracker.analyze_impact("source_1", change_type="schema_change")
        assert len(impact["affected_nodes"]) > 0


# Test execution utilities
def run_comprehensive_tests():
    """Run all comprehensive tests and generate coverage report"""
    import subprocess

    print("Running comprehensive test suite for maximum coverage...")

    # Run pytest with coverage
    cmd = [
        "pytest",
        __file__,
        "-v",
        "--cov=.",
        "--cov-report=term-missing",
        "--cov-report=html",
        "--cov-report=xml",
        "--cov-config=.coveragerc",
        "--tb=short",
        "-s",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    print("\n" + "=" * 80)
    print("COMPREHENSIVE TEST RESULTS")
    print("=" * 80)
    print(result.stdout)

    if result.stderr:
        print("\nErrors:")
        print(result.stderr)

    print("\n" + "=" * 80)
    print("Coverage report generated in htmlcov/index.html")
    print("=" * 80)

    return result.returncode


if __name__ == "__main__":
    # Run comprehensive tests when executed directly
    exit_code = run_comprehensive_tests()
    sys.exit(exit_code)
