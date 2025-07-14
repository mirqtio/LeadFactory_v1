"""
Formula evaluator using xlcalculator for Excel-compatible formulas.

This module provides Excel formula evaluation capabilities for scoring rules,
allowing business users to define complex scoring logic using familiar Excel syntax.
"""
import re
import time
from functools import lru_cache
from typing import Any, Dict, List, Optional, Union

from prometheus_client import Counter, Histogram
from xlcalculator import Evaluator, Model, ModelCompiler
from xlcalculator.xltypes import XLCell

from core.logging import get_logger

from .constants import FORMULA_CACHE_SIZE, FORMULA_EVALUATION_TIMEOUT

logger = get_logger(__name__)

# Metrics
formula_evaluation_time = Histogram(
    "formula_evaluation_duration_seconds", "Time spent evaluating formulas", ["formula_type"]
)

formula_errors = Counter("formula_evaluation_errors_total", "Total number of formula evaluation errors", ["error_type"])


class FormulaEvaluator:
    """Evaluates Excel-style formulas for scoring calculations."""

    def __init__(self, cache_size: int = FORMULA_CACHE_SIZE):
        """
        Initialize the formula evaluator.

        Args:
            cache_size: Number of compiled formulas to cache
        """
        self.cache_size = cache_size
        self._formula_cache: Dict[str, Model] = {}
        self._clear_cache()

    def _clear_cache(self):
        """Clear the formula cache."""
        self._formula_cache.clear()
        # Reset LRU cache
        self._compile_formula.cache_clear()

    @lru_cache(maxsize=FORMULA_CACHE_SIZE)
    def _compile_formula(self, formula: str) -> Model:
        """
        Compile an Excel formula into xlcalculator model.

        Args:
            formula: Excel formula string

        Returns:
            Compiled xlcalculator Model
        """
        # Create a minimal Excel model
        model = Model()

        # Add the formula to cell A1
        model.cells["Sheet1!A1"] = XLCell("Sheet1!A1", formula=formula)

        # Compile the model
        compiler = ModelCompiler()
        compiler.compile(model)

        return model

    def _prepare_context(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare data context for formula evaluation.

        Maps data fields to Excel cell references.

        Args:
            data: Dictionary of variable names to values

        Returns:
            Dictionary mapping cell references to values
        """
        context = {}

        # Map data to cells starting from A2
        # A1 contains the formula, A2 onwards contain data
        for i, (key, value) in enumerate(data.items(), start=2):
            cell_ref = f"Sheet1!A{i}"

            # Create named range for easier reference
            named_ref = key.upper()

            # Store both cell reference and named range
            context[cell_ref] = value
            context[named_ref] = value

            # Also store in row format for array formulas
            col_letter = chr(ord("A") + (i - 2) % 26)
            row_num = 2 + (i - 2) // 26
            context[f"Sheet1!{col_letter}{row_num}"] = value

        return context

    @formula_evaluation_time.labels(formula_type="excel").time()
    def evaluate(
        self, formula: str, data: Dict[str, Any], timeout: float = FORMULA_EVALUATION_TIMEOUT
    ) -> Union[float, int, str, bool, None]:
        """
        Evaluate an Excel formula with given data.

        Args:
            formula: Excel formula string (e.g., "SUM(A2:A5)*1.1")
            data: Dictionary of variable names to values
            timeout: Maximum time allowed for evaluation

        Returns:
            Result of formula evaluation

        Raises:
            ValueError: If formula is invalid
            TimeoutError: If evaluation takes too long
        """
        if not formula:
            return None

        # Normalize formula
        formula = formula.strip()
        if not formula.startswith("="):
            formula = "=" + formula

        start_time = time.time()

        try:
            # Get or compile the formula
            model = self._compile_formula(formula)

            # Check timeout
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Formula compilation exceeded {timeout}s timeout")

            # Prepare context
            context = self._prepare_context(data)

            # Create evaluator with context
            evaluator = Evaluator(model)

            # Set cell values from context
            for cell_ref, value in context.items():
                if cell_ref.startswith("Sheet1!"):
                    try:
                        evaluator.set_cell_value(cell_ref, value)
                    except:
                        # Cell might not exist, ignore
                        pass

            # Check timeout again
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Formula evaluation exceeded {timeout}s timeout")

            # Evaluate the formula cell
            result = evaluator.get_cell_value("Sheet1!A1")

            # Convert result to Python type
            if hasattr(result, "value"):
                result = result.value

            return result

        except TimeoutError:
            formula_errors.labels(error_type="timeout").inc()
            raise
        except Exception as e:
            formula_errors.labels(error_type="evaluation").inc()
            logger.error(f"Formula evaluation error: {e}", extra={"formula": formula, "data_keys": list(data.keys())})
            raise ValueError(f"Formula evaluation failed: {str(e)}")

    def validate_formula(self, formula: str) -> List[str]:
        """
        Validate an Excel formula and return any errors.

        Args:
            formula: Excel formula to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        if not formula:
            errors.append("Formula cannot be empty")
            return errors

        # Normalize formula
        formula = formula.strip()
        if not formula.startswith("="):
            formula = "=" + formula

        try:
            # Try to compile the formula
            self._compile_formula(formula)

            # Check for unsupported functions
            unsupported = self._check_unsupported_functions(formula)
            if unsupported:
                errors.append(f"Unsupported Excel functions: {', '.join(unsupported)}")

        except Exception as e:
            errors.append(f"Invalid formula syntax: {str(e)}")

        return errors

    def _check_unsupported_functions(self, formula: str) -> List[str]:
        """
        Check for Excel functions that xlcalculator doesn't support.

        Args:
            formula: Excel formula string

        Returns:
            List of unsupported function names
        """
        # Common Excel functions that xlcalculator might not support
        # This list should be updated based on xlcalculator capabilities
        unsupported_functions = [
            "XLOOKUP",
            "FILTER",
            "SORT",
            "UNIQUE",
            "SEQUENCE",
            "RANDARRAY",
            "LET",
            "LAMBDA",
            "BYROW",
            "BYCOL",
            "TEXTJOIN",
            "IFS",
            "SWITCH",
            "MAXIFS",
            "MINIFS",
        ]

        # Extract function names from formula
        function_pattern = r"\b([A-Z]+)\s*\("
        found_functions = re.findall(function_pattern, formula.upper())

        # Check which ones are unsupported
        unsupported_found = [func for func in found_functions if func in unsupported_functions]

        return unsupported_found

    def suggest_alternatives(self, unsupported_function: str) -> str:
        """
        Suggest alternatives for unsupported Excel functions.

        Args:
            unsupported_function: Name of unsupported function

        Returns:
            Suggestion for alternative approach
        """
        alternatives = {
            "XLOOKUP": "Use VLOOKUP or INDEX/MATCH instead",
            "FILTER": "Use IF statements with conditions",
            "IFS": "Use nested IF statements",
            "SWITCH": "Use nested IF or CHOOSE function",
            "MAXIFS": "Use MAX with IF array formula",
            "MINIFS": "Use MIN with IF array formula",
            "TEXTJOIN": "Use CONCATENATE or & operator",
        }

        return alternatives.get(unsupported_function.upper(), f"No direct alternative for {unsupported_function}")


# Global evaluator instance
_evaluator_instance: Optional[FormulaEvaluator] = None


def get_formula_evaluator() -> FormulaEvaluator:
    """Get or create the global formula evaluator instance."""
    global _evaluator_instance

    if _evaluator_instance is None:
        _evaluator_instance = FormulaEvaluator()

    return _evaluator_instance


def evaluate_formula(formula: str, data: Dict[str, Any], timeout: float = FORMULA_EVALUATION_TIMEOUT) -> Any:
    """
    Convenience function to evaluate a formula.

    Args:
        formula: Excel formula string
        data: Dictionary of variable names to values
        timeout: Maximum evaluation time

    Returns:
        Result of formula evaluation
    """
    evaluator = get_formula_evaluator()
    return evaluator.evaluate(formula, data, timeout)


def validate_formula(formula: str) -> List[str]:
    """
    Convenience function to validate a formula.

    Args:
        formula: Excel formula to validate

    Returns:
        List of validation errors
    """
    evaluator = get_formula_evaluator()
    return evaluator.validate_formula(formula)
