import numpy as np


def load_data(symbol: str, timeframe: str = "1d", limit: int = 100) -> np.ndarray:
    """
    Mock data loader.
    Returns random walk data for testing: the same series for every symbol and timeframe.

    It uses its own random generator (seeded the same way as before, so the numbers are
    unchanged) instead of re-seeding numpy's global one, which every call used to reset for
    the whole process.
    """
    if limit < 2:
        raise ValueError("limit must be at least 2")

    rng = np.random.RandomState(42)  # Deterministic for testing

    returns = rng.normal(0, 0.02, limit)
    price = 100 * (1 + returns).cumprod()

    return price
