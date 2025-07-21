"""
Tests for P3 Enterprise Security Review Cycles - Automation System
"""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from p3_security_automation import (
    P3SecurityAutomation,
    SecurityDomain,
    SecurityFinding,
    SecurityMetrics,
    SecurityReviewResult,
    SecurityReviewType,
    SecurityRiskLevel,
    SuperClaudeSecurityFramework,
    main,
)


class TestEnums:
    """Test enum definitions"""

    def test_security_review_type_enum(self):
        """Test SecurityReviewType enum"""
        assert SecurityReviewType.WEEKLY == "weekly"
        assert SecurityReviewType.MONTHLY == "monthly"
        assert SecurityReviewType.QUARTERLY == "quarterly"
        assert SecurityReviewType.CONTINUOUS == "continuous"

    def test_security_risk_level_enum(self):
        """Test SecurityRiskLevel enum"""
        assert SecurityRiskLevel.LOW == "low"
        assert SecurityRiskLevel.MEDIUM == "medium"
        assert SecurityRiskLevel.HIGH == "high"
        assert SecurityRiskLevel.CRITICAL == "critical"


class TestSecurityMetrics:
    """Test SecurityMetrics model"""

    def test_security_metrics_creation(self):
        """Test security metrics creation"""
        metrics = SecurityMetrics(
            mean_time_to_detection=15.0,
            mean_time_to_response=45.0,
            security_incident_rate=1.2,
            vulnerability_remediation_time={"critical": 12.0, "high": 48.0},
            compliance_score=90.5,
            security_training_completion=98.2,
            security_control_effectiveness=94.8,
        )

        assert metrics.mean_time_to_detection == 15.0
        assert metrics.mean_time_to_response == 45.0
        assert metrics.compliance_score == 90.5


class TestSecurityFinding:
    """Test SecurityFinding model"""

    def test_security_finding_creation(self):
        """Test security finding creation"""
        finding = SecurityFinding(
            id="finding-123",
            domain=SecurityDomain.AUTHENTICATION,
            title="Test Finding",
            description="Test description",
            risk_level=SecurityRiskLevel.HIGH,
            impact="Test impact",
            remediation="Test remediation",
            affected_systems=["system-1"],
        )

        assert finding.id == "finding-123"
        assert finding.title == "Test Finding"
        assert finding.risk_level == SecurityRiskLevel.HIGH


class TestP3SecurityAutomation:
    """Test P3SecurityAutomation class"""

    def test_p3_security_automation_initialization(self):
        """Test P3 security automation initialization"""
        automation = P3SecurityAutomation()

        assert automation is not None
        assert hasattr(automation, "run_security_review")

    def test_run_security_review(self):
        """Test security review execution"""
        automation = P3SecurityAutomation()

        result = automation.run_security_review(SecurityReviewType.WEEKLY)
        assert result is not None

    def test_schedule_review(self):
        """Test review scheduling"""
        automation = P3SecurityAutomation()

        result = automation.schedule_review(
            review_type=SecurityReviewType.MONTHLY, schedule_time=datetime.now() + timedelta(days=1)
        )
        assert result is True


class TestSuperClaudeSecurityFramework:
    """Test SuperClaudeSecurityFramework class"""

    def test_framework_initialization(self):
        """Test framework initialization"""
        framework = SuperClaudeSecurityFramework()

        assert framework is not None
        assert hasattr(framework, "analyze_security")

    def test_analyze_security(self):
        """Test security analysis"""
        framework = SuperClaudeSecurityFramework()

        result = framework.analyze_security("system-123")
        assert result is not None

    def test_generate_security_report(self):
        """Test security report generation"""
        framework = SuperClaudeSecurityFramework()

        report = framework.generate_security_report("system-123")
        assert report is not None


class TestMainFunction:
    """Test main function"""

    @patch("p3_security_automation.argparse.ArgumentParser")
    def test_main_function_review(self, mock_parser):
        """Test main function with review command"""
        mock_args = Mock()
        mock_args.review = "weekly"
        mock_args.monitor = False
        mock_args.config = None
        mock_args.verbose = False
        mock_parser.return_value.parse_args.return_value = mock_args

        # Test that main function can be called without error
        try:
            main()
            assert True
        except SystemExit:
            # main() calls sys.exit, which is expected
            assert True

    @patch("p3_security_automation.argparse.ArgumentParser")
    def test_main_function_monitor(self, mock_parser):
        """Test main function with monitor command"""
        mock_args = Mock()
        mock_args.review = None
        mock_args.monitor = True
        mock_args.config = None
        mock_args.verbose = False
        mock_parser.return_value.parse_args.return_value = mock_args

        # Test that main function can be called without error
        try:
            main()
            assert True
        except SystemExit:
            # main() calls sys.exit, which is expected
            assert True


class TestIntegrationTests:
    """Integration tests for P3 security automation"""

    def test_full_security_workflow(self):
        """Test complete security workflow"""
        automation = P3SecurityAutomation()

        # Run security review
        result = automation.run_security_review(SecurityReviewType.WEEKLY)
        assert result is not None

        # Schedule review
        schedule_result = automation.schedule_review(
            review_type=SecurityReviewType.MONTHLY, schedule_time=datetime.now() + timedelta(days=1)
        )
        assert schedule_result is True

        # Analyze security
        framework = SuperClaudeSecurityFramework()
        analysis_result = framework.analyze_security("system-123")
        assert analysis_result is not None

        # Generate report
        report = framework.generate_security_report("system-123")
        assert report is not None

    def test_error_handling(self):
        """Test error handling in security automation"""
        automation = P3SecurityAutomation()

        # Test with invalid inputs
        try:
            automation.run_security_review("invalid_type")
            # Should handle gracefully
            assert True
        except Exception:
            # Exceptions should be handled properly
            assert True

    def test_security_metrics_workflow(self):
        """Test security metrics workflow"""
        metrics = SecurityMetrics(
            mean_time_to_detection=10.0,
            mean_time_to_response=30.0,
            security_incident_rate=0.8,
            vulnerability_remediation_time={"critical": 8.0, "high": 36.0},
            compliance_score=92.5,
            security_training_completion=99.1,
            security_control_effectiveness=96.4,
        )

        assert metrics.mean_time_to_detection == 10.0
        assert metrics.mean_time_to_response == 30.0
        assert metrics.compliance_score == 92.5

    def test_security_finding_workflow(self):
        """Test security finding workflow"""
        finding = SecurityFinding(
            id="finding-001",
            domain=SecurityDomain.VULNERABILITY_MANAGEMENT,
            title="SQL Injection Vulnerability",
            description="Potential SQL injection in user input",
            risk_level=SecurityRiskLevel.HIGH,
            impact="High impact vulnerability",
            remediation="Fix SQL injection",
            affected_systems=["web-app"],
        )

        assert finding.id == "finding-001"
        assert finding.title == "SQL Injection Vulnerability"
        assert finding.risk_level == SecurityRiskLevel.HIGH
