"""
Characterization tests: the exact regimes the frozen functions produce on the mock series.

They were recorded from the library when it was reviewed (the arithmetic was checked by hand on small series in test_library.py) and
they pin everything a small series cannot: default windows and thresholds, the unit of the volatility proxy, the length of the warm-up.
A deliberate change to a function changes these numbers; update them in the same commit, and say so.
Each regime is written run-length encoded: (value, how many in a row).
"""

import pytest

from src.library.momentum import rsi_overbought, rsi_oversold
from src.library.trend import price_above_sma, sma_crossover
from src.library.volatility import atr_expansion, bollinger_squeeze
from src.utils.data_loader import load_data


def expand(runs):
    return [value for value, count in runs for _ in range(count)]


PRICES = load_data("BTC")

CASES = {
    "sma_crossover 10/30": (lambda p: sma_crossover(p, 10, 30), [(1, 21), (0, 50), (1, 15), (0, 14)]),
    "sma_crossover default": (sma_crossover, [(1, 33), (0, 49), (1, 17), (0, 1)]),
    "price_above_sma 20": (
        lambda p: price_above_sma(p, 20),
        [(0, 3), (1, 11), (0, 45), (1, 3), (0, 3), (1, 14), (0, 3), (1, 1), (0, 8), (1, 2), (0, 7)],
    ),
    "price_above_sma default": (
        price_above_sma,
        [(1, 19), (0, 1), (1, 3), (0, 48), (1, 3), (0, 1), (1, 4), (0, 3), (1, 2), (0, 2), (1, 2), (0, 1), (1, 6), (0, 5)],
    ),
    "rsi_overbought 7/60": (
        lambda p: rsi_overbought(p, 7, 60),
        [(0, 6), (1, 7), (0, 43), (1, 1), (0, 1), (1, 3), (0, 8), (1, 5), (0, 2), (1, 1), (0, 10), (1, 1), (0, 3), (1, 2), (0, 7)],
    ),
    "rsi_oversold 7/40": (
        lambda p: rsi_oversold(p, 7, 40),
        [(0, 13), (1, 18), (0, 6), (1, 16), (0, 9), (1, 2), (0, 15), (1, 3), (0, 1), (1, 3), (0, 9), (1, 5)],
    ),
    "rsi_overbought default": (rsi_overbought, [(0, 100)]),
    "rsi_oversold default": (rsi_oversold, [(0, 19), (1, 12), (0, 7), (1, 2), (0, 5), (1, 7), (0, 48)]),
    "bollinger_squeeze 10/1.0/0.1": (lambda p: bollinger_squeeze(p, 10, 1.0, 0.1), [(0, 9), (1, 9), (0, 3), (1, 79)]),
    "bollinger_squeeze default": (bollinger_squeeze, [(0, 100)]),
    "atr_expansion 5": (
        lambda p: atr_expansion(p, 5),
        [(0, 14), (1, 4), (0, 2), (1, 5), (0, 6), (1, 5), (0, 1), (1, 2), (0, 1), (1, 2), (0, 5), (1, 7), (0, 8), (1, 6), (0, 5), (1, 6), (0, 16), (1, 1), (0, 1), (1, 3)],
    ),
    "atr_expansion default": (atr_expansion, [(0, 41), (1, 4), (0, 2), (1, 1), (0, 1), (1, 2), (0, 20), (1, 17), (0, 12)]),
}


@pytest.mark.parametrize("name", CASES)
def test_the_regime_on_the_mock_series(name):
    func, runs = CASES[name]
    assert func(PRICES).tolist() == expand(runs)


def test_the_mock_series_itself_is_the_one_the_numbers_were_recorded_on():
    assert len(PRICES) == 100
    assert PRICES[0] == pytest.approx(100.99342830602247)
    assert PRICES[-1] == pytest.approx(79.90354816307004)
    assert PRICES.mean() == pytest.approx(87.62875420120558)
