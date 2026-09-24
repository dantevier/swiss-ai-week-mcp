"""
Mathematical tools for the MCP Boilerplate server.
"""

from ..server import mcp
from ..utils.logger import setup_logger

logger = setup_logger("mcp_boilerplate.tools.math")


@mcp.tool
def add(a: float, b: float) -> float:
    """Add two numbers together."""
    try:
        result = a + b
        logger.debug(f"Addition: {a} + {b} = {result}")
        return result
    except Exception as e:
        logger.error(f"Error in add tool: {e}")
        raise


@mcp.tool
def subtract(a: float, b: float) -> float:
    """Subtract the second number from the first."""
    try:
        result = a - b
        logger.debug(f"Subtraction: {a} - {b} = {result}")
        return result
    except Exception as e:
        logger.error(f"Error in subtract tool: {e}")
        raise


@mcp.tool
def multiply(a: float, b: float) -> float:
    """Multiply two numbers together."""
    try:
        result = a * b
        logger.debug(f"Multiplication: {a} * {b} = {result}")
        return result
    except Exception as e:
        logger.error(f"Error in multiply tool: {e}")
        raise


@mcp.tool
def divide(a: float, b: float) -> float:
    """Divide the first number by the second."""
    try:
        if b == 0:
            raise ValueError("Cannot divide by zero")
        result = a / b
        logger.debug(f"Division: {a} / {b} = {result}")
        return result
    except Exception as e:
        logger.error(f"Error in divide tool: {e}")
        raise


@mcp.tool
def power(base: float, exponent: float) -> float:
    """Raise a number to a power."""
    try:
        result = float(base**exponent)
        logger.debug(f"Power: {base} ^ {exponent} = {result}")
        return result
    except Exception as e:
        logger.error(f"Error in power tool: {e}")
        raise


@mcp.tool
def factorial(n: int) -> int:
    """Calculate the factorial of a non-negative integer."""
    try:
        if n < 0:
            raise ValueError("Factorial is not defined for negative numbers")
        if n > 170:  # Prevent overflow
            raise ValueError("Number too large for factorial calculation")

        result = 1
        for i in range(1, n + 1):
            result *= i

        logger.debug(f"Factorial: {n}! = {result}")
        return result
    except Exception as e:
        logger.error(f"Error in factorial tool: {e}")
        raise
