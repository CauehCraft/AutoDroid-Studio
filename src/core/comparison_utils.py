"""
Comparison utilities for evaluating variable conditions.

This module centralizes comparison logic that was previously duplicated
across automation_engine.py and logic_executors.py.
"""
from typing import Any, Callable, Optional


# Comparison operator functions
def _numeric_compare(left: Any, right: Any, comparator: Callable[[float, float], bool]) -> bool:
    """Safely perform numeric comparison with fallback to string comparison."""
    try:
        f_left = float(left) if left is not None else 0.0
        f_right = float(right)
        return comparator(f_left, f_right)
    except (ValueError, TypeError):
        # Fallback to string comparison
        try:
            return comparator(str(left), str(right))
        except:
            return False


# Comparison operator mapping for cleaner dispatch
COMPARISON_OPERATORS = {
    "==": lambda l, r: str(l) == str(r),
    "!=": lambda l, r: str(l) != str(r),
    ">": lambda l, r: _numeric_compare(l, r, lambda a, b: a > b),
    "<": lambda l, r: _numeric_compare(l, r, lambda a, b: a < b),
    ">=": lambda l, r: _numeric_compare(l, r, lambda a, b: a >= b),
    "<=": lambda l, r: _numeric_compare(l, r, lambda a, b: a <= b),
}


def evaluate_comparison(left: Any, op: str, right: Any) -> bool:
    """
    Evaluate a comparison between two values.
    
    Args:
        left: The left-hand value (e.g., current variable value)
        op: The comparison operator ("==", "!=", ">", "<", ">=", "<=")
        right: The right-hand value (e.g., target value)
    
    Returns:
        bool: Result of the comparison
    """
    comparator = COMPARISON_OPERATORS.get(op)
    return comparator(left, right) if comparator else False


def evaluate_condition(condition: dict, variables: dict) -> bool:
    """
    Evaluate a condition dict against a variables dict.
    
    Args:
        condition: Dict with keys "var", "op", "val"
        variables: Dict of variable name -> value
    
    Returns:
        bool: True if condition passes, False otherwise
    """
    if not condition:
        return True
    
    var_name = condition.get("var")
    op = condition.get("op")
    target_val = condition.get("val")
    
    current_val = variables.get(var_name)
    
    # Handle special existence operators
    if op == "exists":
        return var_name in variables
    if op == "not_exists":
        return var_name not in variables
    
    return evaluate_comparison(current_val, op, target_val)
