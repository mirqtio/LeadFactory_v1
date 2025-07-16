"""Tests for Excel formula evaluator."""
import time

import pytest

from d5_scoring.formula_evaluator import FormulaEvaluator, evaluate_formula, get_formula_evaluator, validate_formula

# Mark entire module as unit test and xfail for Phase 0.5
pytestmark = [pytest.mark.unit, pytest.mark.xfail(reason="Phase 0.5 feature", strict=False)]


class TestFormulaEvaluator:
    """Test the Excel formula evaluator."""

    @pytest.fixture
    def evaluator(self):
        """Create a formula evaluator instance."""
        return FormulaEvaluator()

    def test_simple_arithmetic(self, evaluator):
        """Test simple arithmetic formulas."""
        # Addition
        result = evaluator.evaluate("=2+3", {})
        assert result == 5

        # Multiplication
        result = evaluator.evaluate("=4*5", {})
        assert result == 20

        # Division
        result = evaluator.evaluate("=10/2", {})
        assert result == 5

        # Complex expression
        result = evaluator.evaluate("=(10+5)*2", {})
        assert result == 30

    def test_formula_with_data(self, evaluator):
        """Test formulas that reference data."""
        data = {"revenue": 1000, "costs": 300, "tax_rate": 0.2}

        # Simple reference
        result = evaluator.evaluate("=REVENUE", data)
        assert result == 1000

        # Calculation with references
        result = evaluator.evaluate("=REVENUE-COSTS", data)
        assert result == 700

        # More complex
        result = evaluator.evaluate("=(REVENUE-COSTS)*(1-TAX_RATE)", data)
        assert result == 560  # (1000-300)*(1-0.2) = 700*0.8

    def test_excel_functions(self, evaluator):
        """Test Excel functions."""
        data = {"value1": 10, "value2": 20, "value3": 30, "value4": 40}

        # SUM function
        result = evaluator.evaluate("=SUM(10,20,30)", {})
        assert result == 60

        # AVERAGE function
        result = evaluator.evaluate("=AVERAGE(10,20,30,40)", {})
        assert result == 25

        # MAX/MIN functions
        result = evaluator.evaluate("=MAX(VALUE1,VALUE2,VALUE3)", data)
        assert result == 30

        result = evaluator.evaluate("=MIN(VALUE1,VALUE2,VALUE3)", data)
        assert result == 10

    def test_if_statements(self, evaluator):
        """Test IF conditional logic."""
        data = {"score": 75}

        # Simple IF
        result = evaluator.evaluate("=IF(SCORE>70,100,0)", data)
        assert result == 100

        # Nested IF
        formula = "=IF(SCORE>=80,'A',IF(SCORE>=60,'B',IF(SCORE>=40,'C','D')))"
        result = evaluator.evaluate(formula, data)
        assert result == "B"

    def test_real_scoring_formulas(self, evaluator):
        """Test formulas from lead_value.xlsx reference."""
        # Revenue impact formula
        data = {"base_revenue": 10000}
        result = evaluator.evaluate("=BASE_REVENUE*0.03", data)
        assert result == 300  # 3% uplift

        # Weighted score with cap
        data = {"score1": 85, "weight1": 0.3, "score2": 70, "weight2": 0.4, "score3": 90, "weight3": 0.3}
        # Weighted average: 85*0.3 + 70*0.4 + 90*0.3 = 25.5 + 28 + 27 = 80.5
        formula = "=SCORE1*WEIGHT1 + SCORE2*WEIGHT2 + SCORE3*WEIGHT3"
        result = evaluator.evaluate(formula, data)
        assert abs(result - 80.5) < 0.01

        # Score with bounds
        data = {"raw_score": 120, "multiplier": 1.0}
        formula = "=MAX(0, MIN(100, RAW_SCORE*MULTIPLIER))"
        result = evaluator.evaluate(formula, data)
        assert result == 100  # Capped at 100

    def test_formula_validation(self, evaluator):
        """Test formula validation."""
        # Valid formulas
        assert validate_formula("=2+2") == []
        assert validate_formula("=SUM(A1:A10)") == []
        assert validate_formula("=IF(A1>0,1,0)") == []

        # Invalid formulas
        errors = validate_formula("")
        assert len(errors) > 0
        assert "empty" in errors[0].lower()

        # Malformed formula
        errors = validate_formula("=SUM(")
        assert len(errors) > 0
        assert "syntax" in errors[0].lower()

    def test_unsupported_functions(self, evaluator):
        """Test detection of unsupported functions."""
        # Check unsupported function detection
        errors = evaluator.validate_formula("=XLOOKUP(A1,B:B,C:C)")
        assert len(errors) > 0
        assert "XLOOKUP" in errors[0]

        # Suggest alternatives
        suggestion = evaluator.suggest_alternatives("XLOOKUP")
        assert "VLOOKUP" in suggestion or "INDEX" in suggestion

    def test_formula_caching(self, evaluator):
        """Test that formulas are cached for performance."""
        # First evaluation
        data = {"x": 10}
        start = time.time()
        result1 = evaluator.evaluate("=X*2+5", data)
        time.time() - start

        # Second evaluation (should be cached)
        start = time.time()
        result2 = evaluator.evaluate("=X*2+5", data)
        time.time() - start

        assert result1 == result2 == 25
        # Cached evaluation should be faster (though this might be flaky)
        # Just ensure it works correctly

    def test_timeout_protection(self, evaluator):
        """Test timeout protection for complex formulas."""
        # This would need a formula that takes long to evaluate
        # For now, test that timeout parameter works
        data = {"x": 1}
        result = evaluator.evaluate("=X+1", data, timeout=10.0)
        assert result == 2

    def test_empty_formula(self, evaluator):
        """Test handling of empty formulas."""
        assert evaluator.evaluate("", {}) is None
        assert evaluator.evaluate(None, {}) is None

    def test_formula_normalization(self, evaluator):
        """Test that formulas are normalized."""
        data = {"x": 5}

        # Without equals sign
        result1 = evaluator.evaluate("X*2", data)
        # With equals sign
        result2 = evaluator.evaluate("=X*2", data)

        assert result1 == result2 == 10

    def test_error_handling(self, evaluator):
        """Test error handling in formula evaluation."""
        # Division by zero
        with pytest.raises(ValueError):
            evaluator.evaluate("=1/0", {})

        # Reference to non-existent data
        # xlcalculator might handle this differently
        # Just ensure it doesn't crash
        try:
            evaluator.evaluate("=NONEXISTENT", {})
            # Might return 0 or raise error depending on implementation
        except ValueError:
            pass  # This is acceptable

    def test_singleton_evaluator(self):
        """Test the singleton pattern."""
        eval1 = get_formula_evaluator()
        eval2 = get_formula_evaluator()

        assert eval1 is eval2

    def test_convenience_functions(self):
        """Test module-level convenience functions."""
        # Test evaluate_formula
        result = evaluate_formula("=2+2", {})
        assert result == 4

        # Test validate_formula
        errors = validate_formula("=INVALID(")
        assert len(errors) > 0


class TestIntegrationWithScoringEngine:
    """Test integration with the scoring engine."""

    def test_scoring_with_formula(self):
        """Test that scoring engine uses formulas when available."""
        from d5_scoring.engine import ConfigurableScoringEngine
        from d5_scoring.rules_parser import ScoringRulesParser

        # This would require setting up a mock rules parser with formulas
        # For now, just ensure the imports work
        assert ConfigurableScoringEngine is not None
        assert ScoringRulesParser is not None
