import math
from typing import Protocol

import numpy as np


class RegimeFunction(Protocol):
    """
    Protocol for all frozen quantitative functions.

    Contract:
    - Input: 1D array of prices (float)
    - Output: 1D array of binary states (int) {0, 1} of the same length
    """

    def __call__(self, prices: np.ndarray) -> np.ndarray: ...


def validate_input(prices: np.ndarray) -> None:
    """
    Validates input price array.
    """
    if not isinstance(prices, np.ndarray):
        raise TypeError("Input must be a numpy array")
    if prices.ndim != 1:
        raise ValueError("Input must be a 1D array")
    if not np.issubdtype(prices.dtype, np.floating) and not np.issubdtype(
        prices.dtype, np.integer
    ):
        raise TypeError("Input array must contain numeric values")
    if np.any(np.isnan(prices)) or np.any(np.isinf(prices)):
        raise ValueError("Input array contains NaN or Inf values")
    if len(prices) < 2:
        raise ValueError("Input array must have at least 2 data points")


def validate_output(result: np.ndarray, input_len: int) -> None:
    """
    Validates output regime array.
    """
    if not isinstance(result, np.ndarray):
        raise TypeError("Output must be a numpy array")
    if result.ndim != 1:
        raise ValueError("Output must be a 1D array")
    if len(result) != input_len:
        raise ValueError(f"Output length ({len(result)}) does not match input length ({input_len})")
    if not np.all(np.isin(result, [0, 1])):
        raise ValueError("Output must contain only binary values (0 or 1)")


def check_window(name: str, value: object, minimum: int = 1) -> int:
    """
    Validates a window or period argument: a whole number (not a bool) of at least `minimum`.

    The arguments of a frozen function come from the routing layer, which will be a language
    model: the platform, not the model, decides what is acceptable.
    """
    if isinstance(value, bool) or not isinstance(value, int | np.integer):
        raise TypeError(f"{name} must be an integer, got {type(value).__name__}")
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}, got {value}")
    return int(value)


def check_number(
    name: str, value: object, minimum: float | None = None, maximum: float | None = None
) -> float:
    """
    Validates a numeric argument: a finite real number (not a bool) inside [minimum, maximum].
    """
    if isinstance(value, bool) or not isinstance(value, int | float | np.integer | np.floating):
        raise TypeError(f"{name} must be a number, got {type(value).__name__}")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value}")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be at least {minimum}, got {value}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be at most {maximum}, got {value}")
    return float(value)
