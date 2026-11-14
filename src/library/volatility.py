import numpy as np
import pandas as pd

from src.library.core import check_number, check_window, validate_input, validate_output


def bollinger_squeeze(
    prices: np.ndarray,
    window: int = 20,
    num_std: float = 2.0,
    squeeze_threshold: float = 0.05,
) -> np.ndarray:
    """
    Bollinger Band Squeeze.
    Returns 1 when Bandwidth < Threshold, indicating low volatility consolidation.

    Bandwidth is measured against the size of the average, |SMA|, so a spread (a synthetic
    position such as A-B, which can be zero or negative) is never read as a squeeze just
    because its average is negative.
    """
    validate_input(prices)
    window = check_window("window", window, minimum=2)
    num_std = check_number("num_std", num_std, 0)
    squeeze_threshold = check_number("squeeze_threshold", squeeze_threshold, 0)

    series = pd.Series(prices)
    sma = series.rolling(window=window).mean()
    std = series.rolling(window=window).std()

    upper_band = sma + (std * num_std)
    lower_band = sma - (std * num_std)

    # NaN during the warm-up (and for a zero average): a comparison with NaN is False, so no squeeze is signalled there.
    # (It used to be filled with 1.0, which signalled a squeeze in the warm-up for any threshold above 1.)
    bandwidth = (upper_band - lower_band) / sma.abs()

    regime = np.where(bandwidth < squeeze_threshold, 1, 0)

    validate_output(regime, len(prices))
    return regime.astype(int)


def atr_expansion(prices: np.ndarray, window: int = 14) -> np.ndarray:
    """
    ATR Expansion.
    (Approximation using High-Low from Close prices as we only have Close prices in the interface)
    Returns 1 when Volatility (std dev) is rising above its SMA.
    """
    validate_input(prices)
    window = check_window("window", window, minimum=2)

    series = pd.Series(prices)
    # Using rolling std dev as proxy for ATR since we only have close prices
    volatility = series.pct_change().rolling(window=window).std()
    volatility_sma = volatility.rolling(window=window * 2).mean()

    # Where either is still undefined (the warm-up) the comparison is False: no signal.
    regime = np.where(volatility > volatility_sma, 1, 0)

    validate_output(regime, len(prices))
    return regime.astype(int)
