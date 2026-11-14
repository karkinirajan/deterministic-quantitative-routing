import numpy as np
import pandas as pd

from src.library.core import check_window, validate_input, validate_output


def sma_crossover(prices: np.ndarray, short_window: int = 20, long_window: int = 50) -> np.ndarray:
    """
    Simple Moving Average Crossover.
    Returns 1 when Short SMA > Long SMA, else 0.
    """
    validate_input(prices)
    short_window = check_window("short_window", short_window)
    long_window = check_window("long_window", long_window)

    series = pd.Series(prices)
    short_sma = series.rolling(window=short_window).mean()
    long_sma = series.rolling(window=long_window).mean()

    # The warm-up values are back-filled with the first full-window average, to keep the shape. With a window longer than
    # the data there is no average at all (NaN), and a comparison with NaN is False: no signal. (They used to be filled
    # with 0, which made "short > long" true whenever the other average was negative, as it can be for a spread.)
    short_sma = short_sma.bfill()
    long_sma = long_sma.bfill()

    regime = np.where(short_sma > long_sma, 1, 0)

    validate_output(regime, len(prices))
    return regime.astype(int)


def price_above_sma(prices: np.ndarray, window: int = 50) -> np.ndarray:
    """
    Price above SMA.
    Returns 1 when Price > SMA, else 0.
    """
    validate_input(prices)
    window = check_window("window", window)

    series = pd.Series(prices)
    sma = series.rolling(window=window).mean()
    # Back-filled warm-up values. With a window longer than the data there is no average at all (NaN),
    # and "price > NaN" is False: no signal. (It used to be filled with 0, which made every positive price "above" it.)
    sma = sma.bfill()

    regime = np.where(series > sma, 1, 0)

    validate_output(regime, len(prices))
    return regime.astype(int)
