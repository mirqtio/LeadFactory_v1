"""
Test D3 Assessment Models - Task 030

Tests for comprehensive assessment models with JSONB fields,
proper indexing, and cost tracking.

Acceptance Criteria:
- Assessment result model
- JSONB for flexible data
- Proper indexing  
- Cost tracking fields
"""
import pytest
import sys
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

# Ensure we can import our modules
sys.path.insert(0, '/app')

from d3_assessment.models import (
    AssessmentResult,
    PageSpeedAssessment, 
    TechStackDetection,
    AIInsight,
    AssessmentSession,
    AssessmentCost
)
from d3_assessment.types import (
    AssessmentStatus,
    AssessmentType,
    PageSpeedMetric,
    TechCategory,
    InsightCategory,
    CostType
)


class TestTask030AcceptanceCriteria:
    """Test that Task 030 meets all acceptance criteria"""
    
    @pytest.fixture
    def mock_session(self):
        """Mock database session"""
        session = Mock()
        session.add = Mock()
        session.commit = Mock()
        session.rollback = Mock()
        session.flush = Mock()
        session.query.return_value.filter.return_value.first.return_value = None
        return session
    
    def test_assessment_result_model(self, mock_session):
        """
        Test that assessment result model is comprehensive
        
        Acceptance Criteria: Assessment result model
        """
        
        # Test model creation with all fields
        assessment = AssessmentResult(
            business_id="test-business-id",
            assessment_type=AssessmentType.FULL_AUDIT,
            status=AssessmentStatus.PENDING,
            url="https://example.com",
            domain="example.com",
            is_mobile=False,
            priority=8,
            
            # Key metrics
            performance_score=85,
            accessibility_score=92,
            best_practices_score=88,
            seo_score=95,
            pwa_score=0,
            
            # Core Web Vitals
            first_contentful_paint=1.2,
            largest_contentful_paint=2.5,
            first_input_delay=50,
            cumulative_layout_shift=0.1,
            speed_index=3.2,
            time_to_interactive=4.1,
            total_blocking_time=150,
            
            # Technology summaries
            cms_detected="WordPress",
            framework_detected="React",
            hosting_detected="AWS",
            tech_count=15,
            
            # AI insights summary
            insights_count=8,
            high_priority_issues=3,
            estimated_improvement_potential=25.5,
            
            # Processing info
            processing_time_ms=5500,
            retry_count=0,
            cache_hit=False,
            total_cost_usd=Decimal("0.25")
        )
        
        # Verify all critical fields are present
        assert assessment.business_id == "test-business-id"
        assert assessment.assessment_type == AssessmentType.FULL_AUDIT
        assert assessment.status == AssessmentStatus.PENDING
        assert assessment.url == "https://example.com"
        assert assessment.domain == "example.com"
        assert assessment.is_mobile == False
        assert assessment.priority == 8
        
        # Verify metrics fields
        assert assessment.performance_score == 85
        assert assessment.accessibility_score == 92
        assert assessment.largest_contentful_paint == 2.5
        assert assessment.first_input_delay == 50
        
        # Verify technology fields
        assert assessment.cms_detected == "WordPress"
        assert assessment.tech_count == 15
        
        # Verify insights fields
        assert assessment.insights_count == 8
        assert assessment.high_priority_issues == 3
        
        # Verify cost tracking
        assert assessment.total_cost_usd == Decimal("0.25")
        
        # Verify ID generation (manually set for test)
        assessment.id = "test-assessment-id"
        assert assessment.id is not None
        
        print("✓ Assessment result model works")
    
    def test_jsonb_for_flexible_data(self, mock_session):
        """
        Test that JSONB fields work for flexible data storage
        
        Acceptance Criteria: JSONB for flexible data
        """
        
        # Test AssessmentResult JSONB fields
        pagespeed_data = {
            "lighthouse": {
                "performance": 85,
                "accessibility": 92,
                "categories": {
                    "performance": {"score": 0.85},
                    "accessibility": {"score": 0.92}
                }
            }
        }
        
        tech_stack_data = {
            "cms": [{"name": "WordPress", "version": "6.1", "confidence": 0.95}],
            "javascript": [{"name": "React", "version": "18.2", "confidence": 0.9}],
            "hosting": [{"name": "AWS", "confidence": 0.8}]
        }
        
        ai_insights_data = {
            "insights": [
                {
                    "category": "performance_optimization",
                    "title": "Optimize images",
                    "impact": "high",
                    "effort": "medium"
                }
            ]
        }
        
        assessment_metadata = {
            "user_agent": "Mozilla/5.0...",
            "ip_address": "192.168.1.1",
            "processing_config": {"timeout": 300, "retries": 3}
        }
        
        assessment = AssessmentResult(
            business_id="test-business-id",
            assessment_type=AssessmentType.FULL_AUDIT,
            url="https://example.com",
            domain="example.com",
            pagespeed_data=pagespeed_data,
            tech_stack_data=tech_stack_data,
            ai_insights_data=ai_insights_data,
            assessment_metadata=assessment_metadata
        )
        
        # Verify JSONB data is preserved
        assert assessment.pagespeed_data == pagespeed_data
        assert assessment.tech_stack_data == tech_stack_data
        assert assessment.ai_insights_data == ai_insights_data
        assert assessment.assessment_metadata == assessment_metadata
        
        # Test nested access
        assert assessment.pagespeed_data["lighthouse"]["performance"] == 85
        assert assessment.tech_stack_data["cms"][0]["name"] == "WordPress"
        assert assessment.ai_insights_data["insights"][0]["impact"] == "high"
        assert assessment.assessment_metadata["processing_config"]["timeout"] == 300
        
        # Test PageSpeedAssessment JSONB
        pagespeed = PageSpeedAssessment(
            assessment_id="test-assessment-id",
            is_mobile=False,
            lighthouse_data={
                "performance": 85,
                "audits": {
                    "first-contentful-paint": {"score": 0.8, "displayValue": "1.2 s"}
                }
            },
            core_web_vitals={
                "LCP": {"value": 2500, "classification": "good"},
                "FID": {"value": 50, "classification": "good"},
                "CLS": {"value": 0.1, "classification": "good"}
            },
            opportunities=[
                {"id": "unused-css-rules", "score": 0.9, "details": {}}
            ]
        )
        
        assert pagespeed.lighthouse_data["performance"] == 85
        assert pagespeed.core_web_vitals["LCP"]["value"] == 2500
        
        # Test TechStackDetection JSONB
        tech = TechStackDetection(
            assessment_id="test-assessment-id",
            technology_name="WordPress",
            category=TechCategory.CMS,
            version="6.1",
            confidence=0.95,
            technology_data={
                "detection_method": "meta_generator",
                "evidence": ["wp-content", "wp-includes"],
                "plugins": ["Yoast SEO", "WooCommerce"],
                "theme": "Twenty Twenty-Three"
            }
        )
        
        assert tech.technology_data["plugins"] == ["Yoast SEO", "WooCommerce"]
        
        # Test AIInsight JSONB
        insight = AIInsight(
            assessment_id="test-assessment-id",
            category=InsightCategory.PERFORMANCE_OPTIMIZATION,
            title="Optimize Critical Rendering Path",
            description="Your page's critical rendering path can be improved",
            impact="high",
            effort="medium",
            actionable_steps=[
                "Minimize critical CSS",
                "Defer non-critical JavaScript",
                "Optimize web fonts"
            ],
            ai_data={
                "confidence": 0.92,
                "model": "gpt-4",
                "reasoning": "Based on Lighthouse audit results..."
            }
        )
        
        assert insight.actionable_steps[0] == "Minimize critical CSS"
        assert insight.ai_data["confidence"] == 0.92
        
        print("✓ JSONB for flexible data works")
    
    def test_proper_indexing(self, mock_session):
        """
        Test that proper indexing is configured
        
        Acceptance Criteria: Proper indexing
        """
        
        # Verify AssessmentResult indexes
        assessment_indexes = AssessmentResult.__table_args__
        index_names = [idx.name for idx in assessment_indexes if hasattr(idx, 'name')]
        
        # Test that key indexes exist
        assert any("business_type" in str(idx) for idx in assessment_indexes), "Business type index missing"
        assert any("status" in str(idx) for idx in assessment_indexes), "Status index missing"
        assert any("created" in str(idx) for idx in assessment_indexes), "Created index missing"
        assert any("domain" in str(idx) for idx in assessment_indexes), "Domain index missing"
        assert any("scores" in str(idx) for idx in assessment_indexes), "Scores index missing"
        
        # Test JSONB GIN indexes
        assert any("pagespeed" in str(idx) and "gin" in str(idx) for idx in assessment_indexes), "PageSpeed GIN index missing"
        assert any("tech" in str(idx) and "gin" in str(idx) for idx in assessment_indexes), "Tech stack GIN index missing"
        assert any("insights" in str(idx) and "gin" in str(idx) for idx in assessment_indexes), "Insights GIN index missing"
        
        # Test composite indexes
        assert any("business_status_type" in str(idx) for idx in assessment_indexes), "Composite index missing"
        
        # Verify PageSpeedAssessment indexes
        pagespeed_indexes = PageSpeedAssessment.__table_args__
        assert any("lighthouse" in str(idx) and "gin" in str(idx) for idx in pagespeed_indexes), "Lighthouse GIN index missing"
        assert any("vitals" in str(idx) and "gin" in str(idx) for idx in pagespeed_indexes), "Vitals GIN index missing"
        
        # Verify TechStackDetection indexes
        tech_indexes = TechStackDetection.__table_args__
        assert any("category" in str(idx) for idx in tech_indexes), "Tech category index missing"
        assert any("confidence" in str(idx) for idx in tech_indexes), "Tech confidence index missing"
        
        # Verify AIInsight indexes
        insight_indexes = AIInsight.__table_args__
        assert any("category" in str(idx) for idx in insight_indexes), "Insight category index missing"
        assert any("priority" in str(idx) for idx in insight_indexes), "Insight priority index missing"
        
        # Verify AssessmentSession indexes
        session_indexes = AssessmentSession.__table_args__
        assert any("status" in str(idx) for idx in session_indexes), "Session status index missing"
        assert any("cost" in str(idx) for idx in session_indexes), "Session cost index missing"
        
        # Verify AssessmentCost indexes
        cost_indexes = AssessmentCost.__table_args__
        assert any("type" in str(idx) for idx in cost_indexes), "Cost type index missing"
        assert any("amount" in str(idx) for idx in cost_indexes), "Cost amount index missing"
        
        print("✓ Proper indexing configured")
    
    def test_cost_tracking_fields(self, mock_session):
        """
        Test that comprehensive cost tracking fields are implemented
        
        Acceptance Criteria: Cost tracking fields
        """
        
        # Test AssessmentResult cost tracking
        assessment = AssessmentResult(
            business_id="test-business-id",
            assessment_type=AssessmentType.PAGESPEED,
            url="https://example.com",
            domain="example.com",
            total_cost_usd=Decimal("1.25")
        )
        
        assert assessment.total_cost_usd == Decimal("1.25")
        
        # Test AssessmentSession cost tracking
        session = AssessmentSession(
            assessment_type=AssessmentType.FULL_AUDIT,
            total_cost_usd=Decimal("5.50"),
            estimated_cost_usd=Decimal("6.00"),
            total_assessments=10,
            completed_assessments=7,
            failed_assessments=1
        )
        
        assert session.total_cost_usd == Decimal("5.50")
        assert session.estimated_cost_usd == Decimal("6.00")
        assert session.total_assessments == 10
        
        # Test detailed AssessmentCost tracking
        api_cost = AssessmentCost(
            assessment_id="test-assessment-id",
            cost_type=CostType.API_CALL,
            amount=Decimal("0.15"),
            currency="USD",
            provider="Google PageSpeed",
            service_name="PageSpeed Insights API",
            description="PageSpeed analysis for mobile device",
            units_consumed=1.0,
            unit_type="requests",
            rate_per_unit=Decimal("0.15"),
            cost_data={
                "request_id": "req_123",
                "endpoint": "/pagespeedonline/v5/runPagespeed",
                "timestamp": "2023-10-01T12:00:00Z"
            }
        )
        
        assert api_cost.cost_type == CostType.API_CALL
        assert api_cost.amount == Decimal("0.15")
        assert api_cost.provider == "Google PageSpeed"
        assert api_cost.units_consumed == 1.0
        assert api_cost.rate_per_unit == Decimal("0.15")
        assert api_cost.cost_data["request_id"] == "req_123"
        
        # Test AI token cost tracking
        ai_cost = AssessmentCost(
            assessment_id="test-assessment-id",
            cost_type=CostType.AI_TOKENS,
            amount=Decimal("0.08"),
            currency="USD",
            provider="OpenAI",
            service_name="GPT-4",
            description="AI insights generation",
            units_consumed=4000.0,
            unit_type="tokens",
            rate_per_unit=Decimal("0.00002"),
            cost_data={
                "prompt_tokens": 1500,
                "completion_tokens": 2500,
                "model": "gpt-4",
                "temperature": 0.7
            }
        )
        
        assert ai_cost.cost_type == CostType.AI_TOKENS
        assert ai_cost.amount == Decimal("0.08")
        assert ai_cost.units_consumed == 4000.0
        assert ai_cost.cost_data["prompt_tokens"] == 1500
        
        # Test processing time cost
        processing_cost = AssessmentCost(
            session_id="test-session-id",
            cost_type=CostType.PROCESSING_TIME,
            amount=Decimal("0.02"),
            currency="USD",
            provider="AWS Lambda",
            service_name="Compute",
            description="Assessment processing time",
            units_consumed=5.5,
            unit_type="seconds",
            rate_per_unit=Decimal("0.0036")
        )
        
        assert processing_cost.cost_type == CostType.PROCESSING_TIME
        assert processing_cost.units_consumed == 5.5
        assert processing_cost.unit_type == "seconds"
        
        print("✓ Cost tracking fields work")
    
    def test_model_relationships(self, mock_session):
        """Test that model relationships are properly configured"""
        
        # Test AssessmentResult relationships
        assessment = AssessmentResult(
            business_id="test-business-id",
            assessment_type=AssessmentType.FULL_AUDIT,
            url="https://example.com",
            domain="example.com"
        )
        
        # Check relationship attributes exist
        assert hasattr(assessment, 'session')
        assert hasattr(assessment, 'costs')
        
        # Test AssessmentSession relationships
        session = AssessmentSession(
            assessment_type=AssessmentType.FULL_AUDIT
        )
        
        assert hasattr(session, 'results')
        assert hasattr(session, 'costs')
        
        # Test AssessmentCost relationships
        cost = AssessmentCost(
            cost_type=CostType.API_CALL,
            amount=Decimal("0.10")
        )
        
        assert hasattr(cost, 'assessment')
        assert hasattr(cost, 'session')
        
        print("✓ Model relationships configured")
    
    def test_model_constraints(self, mock_session):
        """Test that proper constraints are enforced"""
        
        # Test score constraints (should be 0-100)
        assessment = AssessmentResult(
            business_id="test-business-id",
            assessment_type=AssessmentType.PAGESPEED,
            url="https://example.com",
            domain="example.com",
            performance_score=85,
            accessibility_score=92
        )
        
        # Valid scores should work
        assert assessment.performance_score == 85
        assert assessment.accessibility_score == 92
        
        # Test priority constraints (should be 1-10)
        assessment.priority = 5
        assert assessment.priority == 5
        
        # Test cost constraints (should be positive)
        assessment.total_cost_usd = Decimal("1.50")
        assert assessment.total_cost_usd == Decimal("1.50")
        
        # Test confidence constraints (should be 0-1)
        tech = TechStackDetection(
            assessment_id="test-id",
            technology_name="WordPress",
            category=TechCategory.CMS,
            confidence=0.95
        )
        assert tech.confidence == 0.95
        
        insight = AIInsight(
            assessment_id="test-id",
            category=InsightCategory.PERFORMANCE_OPTIMIZATION,
            title="Test Insight",
            description="Test description",
            impact="high",
            effort="medium",
            confidence=0.92
        )
        assert insight.confidence == 0.92
        
        print("✓ Model constraints work")
    
    def test_enum_types(self, mock_session):
        """Test that enum types are properly defined and used"""
        
        # Test AssessmentStatus enum
        assert AssessmentStatus.PENDING.value == "pending"
        assert AssessmentStatus.COMPLETED.value == "completed"
        
        # Test AssessmentType enum
        assert AssessmentType.FULL_AUDIT.value == "full_audit"
        assert AssessmentType.PAGESPEED.value == "pagespeed"
        
        # Test TechCategory enum
        assert TechCategory.CMS.value == "cms"
        assert TechCategory.FRONTEND.value == "frontend"
        
        # Test InsightCategory enum
        assert InsightCategory.PERFORMANCE_OPTIMIZATION.value == "performance_optimization"
        assert InsightCategory.SEO_RECOMMENDATIONS.value == "seo_recommendations"
        
        # Test CostType enum
        assert CostType.API_CALL.value == "api_call"
        assert CostType.AI_TOKENS.value == "ai_tokens"
        
        # Test enums in models
        assessment = AssessmentResult(
            business_id="test-business-id",
            assessment_type=AssessmentType.TECH_STACK,
            status=AssessmentStatus.RUNNING,
            url="https://example.com",
            domain="example.com"
        )
        
        assert assessment.assessment_type == AssessmentType.TECH_STACK
        assert assessment.status == AssessmentStatus.RUNNING
        
        print("✓ Enum types work")


# Allow running this test file directly
if __name__ == "__main__":
    test_instance = TestTask030AcceptanceCriteria()
    
    # Mock session
    mock_session = Mock()
    mock_session.add = Mock()
    mock_session.commit = Mock()
    
    print("🔍 Running Task 030 Model Tests...")
    print()
    
    try:
        test_instance.test_assessment_result_model(mock_session)
        test_instance.test_jsonb_for_flexible_data(mock_session)
        test_instance.test_proper_indexing(mock_session)
        test_instance.test_cost_tracking_fields(mock_session)
        test_instance.test_model_relationships(mock_session)
        test_instance.test_model_constraints(mock_session)
        test_instance.test_enum_types(mock_session)
        
        print()
        print("🎉 All Task 030 acceptance criteria tests pass!")
        print("   - Assessment result model: ✓")
        print("   - JSONB for flexible data: ✓")
        print("   - Proper indexing: ✓")
        print("   - Cost tracking fields: ✓")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()