"""Tests for the SymPy calculate tool handler logic."""
import pytest
from sympy import (
    sqrt, sin, cos, tan, asin, acos, atan,
    log, exp, pi, E, oo, I, symbols, solve, diff,
    integrate, simplify, expand, factor, limit,
    Rational, Abs, ceiling, floor, gcd, lcm,
    Matrix, summation, product
)
from sympy.parsing.sympy_parser import parse_expr


# Replicate the allowed_locals from the handler
x, y, z, n, k = symbols('x y z n k')
ALLOWED_LOCALS = {
    "sqrt": sqrt, "sin": sin, "cos": cos, "tan": tan,
    "asin": asin, "acos": acos, "atan": atan,
    "log": log, "exp": exp, "pi": pi, "E": E,
    "oo": oo, "I": I, "Abs": Abs,
    "ceiling": ceiling, "floor": floor,
    "gcd": gcd, "lcm": lcm,
    "x": x, "y": y, "z": z, "n": n, "k": k,
    "solve": solve, "diff": diff, "integrate": integrate,
    "simplify": simplify, "expand": expand, "factor": factor,
    "limit": limit, "Rational": Rational,
    "Matrix": Matrix, "summation": summation, "product": product,
    "symbols": symbols,
}


def _make_safe_global_dict() -> dict:
    """Build a SymPy global_dict with builtins stripped out."""
    gd = {}
    exec("from sympy import *", gd)  # noqa: S102
    gd.pop("__builtins__", None)
    return gd


_SAFE_GLOBAL_DICT = _make_safe_global_dict()


def evaluate(expression: str) -> str:
    """Mirror the handler logic for testing."""
    result = parse_expr(
        expression,
        local_dict=ALLOWED_LOCALS,
        global_dict=_SAFE_GLOBAL_DICT,
        transformations="all",
    )
    if hasattr(result, 'doit'):
        result = result.doit()
    return str(result)


class TestCalculateArithmetic:
    def test_basic_multiplication(self):
        assert evaluate("3 * 5") == "15"

    def test_addition_and_sqrt(self):
        assert evaluate("3 * 5 + sqrt(16)") == "19"

    def test_division(self):
        assert evaluate("100 / 4") == "25"

    def test_power(self):
        assert evaluate("2**10") == "1024"


class TestCalculateAlgebra:
    def test_solve_quadratic(self):
        result = evaluate("solve(x**2 - 9, x)")
        assert result == "[-3, 3]"

    def test_expand(self):
        result = evaluate("expand((x + 1)**2)")
        assert result == "x**2 + 2*x + 1"

    def test_factor(self):
        result = evaluate("factor(x**2 - 4)")
        assert result == "(x - 2)*(x + 2)"


class TestCalculateCalculus:
    def test_differentiate(self):
        result = evaluate("diff(x**3 + 2*x, x)")
        assert result == "3*x**2 + 2"

    def test_integrate(self):
        result = evaluate("integrate(x**2, x)")
        assert result == "x**3/3"


class TestCalculateConstants:
    def test_pi(self):
        result = evaluate("pi")
        assert result == "pi"

    def test_euler(self):
        result = evaluate("E")
        assert result == "E"


class TestCalculateErrors:
    def test_invalid_expression(self):
        with pytest.raises(Exception):
            evaluate("this is not math ][")

    def test_no_os_access(self):
        """Verify that dangerous builtins are not accessible."""
        with pytest.raises(Exception):
            evaluate("__import__('os').system('echo pwned')")
