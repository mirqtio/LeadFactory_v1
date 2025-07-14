"""Omega (online dependence) calculator for impact scaling."""
import ast
import operator
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

# Define allowed operators for safe evaluation
ALLOWED_OPS = {
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.And: operator.and_,
    ast.Or: operator.or_,
    ast.Not: operator.not_,
    ast.In: lambda x, y: x in y,
    ast.NotIn: lambda x, y: x not in y,
}


@lru_cache(maxsize=1)
def _load_omega_rules():
    """Load omega rules from YAML."""
    yaml_path = Path(__file__).parent.parent / "config" / "online_dependence.yaml"
    with open(yaml_path, "r") as f:
        return yaml.safe_load(f)


def _safe_eval(node, context: Dict[str, Any]):
    """Safely evaluate AST node with given context."""
    if isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.Name):
        if node.id in context:
            return context[node.id]
        elif node.id in ["True", "False", "None"]:
            return eval(node.id)
        else:
            raise ValueError(f"Unknown variable: {node.id}")
    elif isinstance(node, ast.BinOp):
        raise ValueError("Binary operations not allowed")
    elif isinstance(node, ast.UnaryOp):
        op_func = ALLOWED_OPS.get(type(node.op))
        if op_func:
            return op_func(_safe_eval(node.operand, context))
        raise ValueError(f"Unsupported operation: {type(node.op)}")
    elif isinstance(node, ast.Compare):
        left = _safe_eval(node.left, context)
        for op, right in zip(node.ops, node.comparators):
            op_func = ALLOWED_OPS.get(type(op))
            if not op_func:
                raise ValueError(f"Unsupported comparison: {type(op)}")
            right_val = _safe_eval(right, context)
            if not op_func(left, right_val):
                return False
            left = right_val
        return True
    elif isinstance(node, ast.BoolOp):
        op_func = ALLOWED_OPS.get(type(node.op))
        if not op_func:
            raise ValueError(f"Unsupported boolean operation: {type(node.op)}")
        values = [_safe_eval(v, context) for v in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        elif isinstance(node.op, ast.Or):
            return any(values)
    elif isinstance(node, ast.List):
        return [_safe_eval(item, context) for item in node.elts]
    elif isinstance(node, ast.Str):  # For Python < 3.8 compatibility
        return node.s
    else:
        raise ValueError(f"Unsupported node type: {type(node)}")


def evaluate_condition(condition: str, context: Dict[str, Any]) -> bool:
    """
    Safely evaluate a condition string with given context.

    Args:
        condition: Condition string to evaluate
        context: Dictionary of variables and their values

    Returns:
        bool: Result of condition evaluation
    """
    try:
        # Parse the condition
        tree = ast.parse(condition, mode="eval")

        # Evaluate safely
        return _safe_eval(tree.body, context)
    except Exception as e:
        # Log error and return False for invalid conditions
        print(f"Error evaluating condition '{condition}': {e}")
        return False


def calculate_omega(
    visits_per_mil: Optional[int] = None,
    commercial_kw_pct: Optional[int] = None,
    vertical: Optional[str] = None,
    has_online_ordering: Optional[bool] = None,
    business_type: Optional[str] = None,
    **kwargs,
) -> float:
    """
    Calculate omega (online dependence factor) based on business characteristics.

    Args:
        visits_per_mil: Monthly visits per $1M revenue
        commercial_kw_pct: Percentage of commercial intent keywords
        vertical: Business vertical/industry
        has_online_ordering: Whether business has online ordering
        business_type: B2B or B2C classification
        **kwargs: Additional variables for rule evaluation

    Returns:
        float: Omega value (typically 0.4 to 1.2)
    """
    # Load rules
    config = _load_omega_rules()
    rules = config["rules"]
    variables = config["variables"]

    # Build context with defaults
    context = {}

    # Add provided values or use defaults
    for var_name, var_config in variables.items():
        if var_name == "visits_per_mil" and visits_per_mil is not None:
            context[var_name] = visits_per_mil
        elif var_name == "commercial_kw_pct" and commercial_kw_pct is not None:
            context[var_name] = commercial_kw_pct
        elif var_name == "vertical" and vertical is not None:
            context[var_name] = vertical
        elif var_name == "has_online_ordering" and has_online_ordering is not None:
            context[var_name] = has_online_ordering
        elif var_name == "business_type" and business_type is not None:
            context[var_name] = business_type
        else:
            context[var_name] = var_config["default"]

    # Add any additional kwargs
    context.update(kwargs)

    # Evaluate rules in order
    for rule in rules:
        condition = rule["condition"]
        if evaluate_condition(condition, context):
            return float(rule["omega"])

    # Should never reach here if default rule exists
    return 1.0
