import math
import ast
import operator as op
from langchain_core.tools import tool

# =========================================================
# SAFE EVAL ENGINE
# =========================================================

SAFE_OPS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Pow: op.pow,
    ast.USub: op.neg,
}

SAFE_FUNCTIONS = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
}

# =========================================================
# TOOL DEFINITIONS
# =========================================================

@tool
def safe_eval(expr: str) -> float:
    """
    Safely evaluate mathematical expressions.

    Example:
    - (2+3)*5
    - sqrt(81)+10
    """

    def eval_node(node):

        # numbers
        if isinstance(node, ast.Constant):
            return node.value

        # binary operators
        if isinstance(node, ast.BinOp):
            return SAFE_OPS[type(node.op)](
                eval_node(node.left),
                eval_node(node.right),
            )

        # unary operators
        if isinstance(node, ast.UnaryOp):
            return SAFE_OPS[type(node.op)](
                eval_node(node.operand)
            )

        # function calls
        if isinstance(node, ast.Call):

            if not isinstance(node.func, ast.Name):
                raise ValueError("Invalid function call")

            func_name = node.func.id

            if func_name not in SAFE_FUNCTIONS:
                raise ValueError(
                    f"Function '{func_name}' is not allowed"
                )

            args = [eval_node(arg) for arg in node.args]

            return SAFE_FUNCTIONS[func_name](*args)

        raise ValueError(
            f"Unsupported operation: {type(node)}"
        )

    tree = ast.parse(expr, mode="eval")

    return eval_node(tree.body)


# ---------------------------------------------------------

@tool
def add(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b


@tool
def subtract(a: float, b: float) -> float:
    """Subtract b from a."""
    return a - b


@tool
def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b


@tool
def divide(a: float, b: float) -> float:
    """Divide a by b."""
    if b == 0:
        raise ValueError("Division by zero")
    return a / b


@tool
def power(a: float, b: float) -> float:
    """Compute a raised to power b."""
    return math.pow(a, b)


@tool
def sqrt(x: float) -> float:
    """Square root of a number."""
    return math.sqrt(x)


@tool
def nth_root(x: float, n: float) -> float:
    """Compute nth root of x."""
    return x ** (1 / n)


@tool
def percentage(value: float, percent: float) -> float:
    """Compute percentage of a value."""
    return (value * percent) / 100


@tool
def percent_change(old: float, new: float) -> float:
    """Calculate percentage change."""
    return ((new - old) / old) * 100

tools: list= [add, subtract, multiply, divide, power, sqrt, nth_root, percentage, percent_change, safe_eval,]