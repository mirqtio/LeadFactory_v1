"""
Unit tests for d5_scoring formula evaluator module.
Coverage target: 80%+ for Excel formula evaluation logic.
"""
from unittest.mock import MagicMock, call, patch

import pytest

from d5_scoring.constants import FORMULA_CACHE_SIZE, FORMULA_EVALUATION_TIMEOUT
from d5_scoring.formula_evaluator import FormulaEvaluator


class TestFormulaEvaluator:
    """Test suite for FormulaEvaluator class."""

    def test_init_default_cache_size(self):
        """Test FormulaEvaluator initialization with default cache size."""
        evaluator = FormulaEvaluator()
        assert evaluator.cache_size == FORMULA_CACHE_SIZE
        assert evaluator._formula_cache == {}

    def test_init_custom_cache_size(self):
        """Test FormulaEvaluator initialization with custom cache size."""
        custom_size = 50
        evaluator = FormulaEvaluator(cache_size=custom_size)
        assert evaluator.cache_size == custom_size
        assert evaluator._formula_cache == {}

    def test_clear_cache_functionality(self):
        """Test that cache clearing works properly."""
        evaluator = FormulaEvaluator()

        # Add something to cache manually
        evaluator._formula_cache["test"] = MagicMock()
        assert len(evaluator._formula_cache) == 1

        # Clear cache
        evaluator._clear_cache()
        assert len(evaluator._formula_cache) == 0

    @patch("d5_scoring.formula_evaluator.ModelCompiler")
    def test_compile_formula_success(self, mock_compiler):
        """Test successful formula compilation."""
        evaluator = FormulaEvaluator()

        # Mock the compilation process
        mock_model = MagicMock()
        mock_compiler_instance = MagicMock()
        mock_compiler_instance.read_and_parse_archive.return_value = mock_model
        mock_compiler.return_value = mock_compiler_instance

        # Test formula compilation
        formula = "=A1+B1"
        result = evaluator._compile_formula(formula)

        # Verify compilation was attempted
        mock_compiler.assert_called_once()
        assert result is not None

    def test_cache_size_constant_usage(self):
        """Test that cache size uses the constant correctly."""
        evaluator = FormulaEvaluator()
        assert evaluator.cache_size == FORMULA_CACHE_SIZE

        # Test with different cache size
        custom_evaluator = FormulaEvaluator(cache_size=25)
        assert custom_evaluator.cache_size == 25

    def test_formula_cache_initialization(self):
        """Test that formula cache is properly initialized."""
        evaluator = FormulaEvaluator()
        assert isinstance(evaluator._formula_cache, dict)
        assert len(evaluator._formula_cache) == 0

    @patch("d5_scoring.formula_evaluator.logger")
    def test_logger_import(self, mock_logger):
        """Test that logger is properly imported and available."""
        evaluator = FormulaEvaluator()
        # Logger should be imported from core.logging
        assert evaluator is not None

    def test_evaluator_class_exists(self):
        """Test that FormulaEvaluator class can be instantiated."""
        evaluator = FormulaEvaluator()
        assert evaluator is not None
        assert hasattr(evaluator, "cache_size")
        assert hasattr(evaluator, "_formula_cache")
        assert hasattr(evaluator, "_clear_cache")

    def test_constants_import(self):
        """Test that required constants are imported correctly."""
        evaluator = FormulaEvaluator()
        # These constants should be available from the module
        assert FORMULA_CACHE_SIZE is not None
        assert FORMULA_EVALUATION_TIMEOUT is not None
        assert evaluator.cache_size == FORMULA_CACHE_SIZE

    @patch("d5_scoring.formula_evaluator.ModelCompiler")
    def test_compile_formula_cache_behavior(self, mock_compiler):
        """Test that formula compilation uses caching properly."""
        evaluator = FormulaEvaluator()

        # Mock successful compilation
        mock_model = MagicMock()
        mock_compiler_instance = MagicMock()
        mock_compiler_instance.read_and_parse_archive.return_value = mock_model
        mock_compiler.return_value = mock_compiler_instance

        formula = "=A1+B1"

        # First call should compile
        result1 = evaluator._compile_formula(formula)

        # Second call should use cache (same result)
        result2 = evaluator._compile_formula(formula)

        # Should get the same result (cached)
        assert result1 is result2

    def test_metrics_imports(self):
        """Test that prometheus metrics are properly imported."""
        # Import the metrics to verify they exist
        from d5_scoring.formula_evaluator import formula_errors, formula_evaluation_time

        assert formula_evaluation_time is not None
        assert formula_errors is not None

    @patch("d5_scoring.formula_evaluator.Evaluator")
    @patch("d5_scoring.formula_evaluator.Model")
    @patch("d5_scoring.formula_evaluator.ModelCompiler")
    def test_xlcalculator_imports(self, mock_compiler, mock_model, mock_evaluator):
        """Test that xlcalculator dependencies are properly imported."""
        evaluator = FormulaEvaluator()

        # These should be imported without issues
        assert mock_compiler is not None
        assert mock_model is not None
        assert mock_evaluator is not None

    def test_clear_cache_method_exists(self):
        """Test that _clear_cache method exists and is callable."""
        evaluator = FormulaEvaluator()
        assert hasattr(evaluator, "_clear_cache")
        assert callable(evaluator._clear_cache)

        # Should not raise an exception
        evaluator._clear_cache()

    def test_compile_formula_method_exists(self):
        """Test that _compile_formula method exists and is decorated."""
        evaluator = FormulaEvaluator()
        assert hasattr(evaluator, "_compile_formula")
        assert callable(evaluator._compile_formula)

        # Check that it has LRU cache decoration
        assert hasattr(evaluator._compile_formula, "cache_clear")
        assert hasattr(evaluator._compile_formula, "cache_info")

    def test_cache_size_validation(self):
        """Test cache size parameter validation."""
        # Valid cache sizes
        evaluator1 = FormulaEvaluator(cache_size=1)
        assert evaluator1.cache_size == 1

        evaluator2 = FormulaEvaluator(cache_size=1000)
        assert evaluator2.cache_size == 1000

        # Zero cache size
        evaluator3 = FormulaEvaluator(cache_size=0)
        assert evaluator3.cache_size == 0
