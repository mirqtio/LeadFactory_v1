"""
Budget Monitor - Test stub implementation for performance testing

This module provides the BudgetMonitor and BudgetStatus classes that are
referenced in performance tests. This is a minimal implementation to support
testing infrastructure.
"""
from decimal import Decimal
from enum import Enum
from typing import Dict, Optional


class BudgetStatus(Enum):
    """Budget status enumeration"""

    OK = "ok"
    WARNING = "warning"
    STOP = "stop"


class BudgetMonitor:
    """
    Simple budget monitoring class for performance testing

    This is a test stub that provides the interface expected by
    performance tests without full production functionality.
    """

    def __init__(
        self, monthly_budget_usd: float, warning_threshold: float = 0.8, stop_threshold: float = 0.95, session=None
    ):
        """
        Initialize budget monitor

        Args:
            monthly_budget_usd: Monthly budget limit in USD
            warning_threshold: Threshold for warning alerts (0.8 = 80%)
            stop_threshold: Threshold for stopping operations (0.95 = 95%)
            session: Database session (unused in stub)
        """
        self.monthly_budget_usd = Decimal(str(monthly_budget_usd))
        self.warning_threshold = warning_threshold
        self.stop_threshold = stop_threshold
        self.session = session

    def check_budget_status(self, current_spend: float) -> BudgetStatus:
        """
        Check current budget status

        Args:
            current_spend: Current spending amount in USD

        Returns:
            BudgetStatus indicating current status
        """
        current_spend_decimal = Decimal(str(current_spend))
        usage_ratio = float(current_spend_decimal / self.monthly_budget_usd)

        if usage_ratio >= self.stop_threshold:
            return BudgetStatus.STOP
        elif usage_ratio >= self.warning_threshold:
            return BudgetStatus.WARNING
        else:
            return BudgetStatus.OK

    def get_budget_summary(self) -> Dict[str, float]:
        """
        Get budget summary information

        Returns:
            Dictionary with budget summary data
        """
        return {
            "monthly_budget_usd": float(self.monthly_budget_usd),
            "warning_threshold": self.warning_threshold,
            "stop_threshold": self.stop_threshold,
        }
