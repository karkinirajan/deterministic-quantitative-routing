import numpy as np
import pytest

from src.library.momentum import calculate_rsi, rsi_overbought, rsi_oversold
from src.library.trend import price_above_sma, sma_crossover
from src.library.volatility import atr_expansion, bollinger_squeeze

RISING = np.arange(1.0, 7.0)  # 1..6
FALLING = RISING[::-1].copy()


@pytest.fixture
def sample_prices():
    # Simple sine wave + linear trend
    x = np.linspace(0, 100, 200)
    return 100 + x + 10 * np.sin(x)


def test_sma_crossover(sample_prices):
    regime = sma_crossover(sample_prices, short_window=10, long_window=20)
    assert len(regime) == len(sample_prices)
    assert np.all(np.isin(regime, [0, 1]))
    # Basic logic check: if prices rising, short SMA > long SMA eventually
    assert regime[-1] == 1


def test_bollinger_squeeze():
    # Constant prices -> 0 std dev -> squeeze
    prices = np.ones(100) * 100
    regime = bollinger_squeeze(prices, squeeze_threshold=0.1)
    assert np.all(regime[20:] == 1)  # Squeeze should be active after window


def test_rsi_overbought():
    # Rapidly increasing prices -> high RSI
    prices = np.array([100 * (1.1**i) for i in range(50)])
    regime = rsi_overbought(prices, threshold=70)
    assert regime[-1] == 1


def test_rsi_oversold():
    # Rapidly decreasing prices -> low RSI
    prices = np.array([100 * (0.9**i) for i in range(50)])
    regime = rsi_oversold(prices, threshold=30)
    assert regime[-1] == 1


class TestSmaCrossoverValues:
    def test_rising_prices(self):
        # short SMA (2): 1.5 1.5 2.5 3.5 4.5 5.5; long SMA (3): 2 2 2 3 4 5 (leading NaNs back-filled)
        assert sma_crossover(RISING, short_window=2, long_window=3).tolist() == [0, 0, 1, 1, 1, 1]

    def test_falling_prices(self):
        assert sma_crossover(FALLING, short_window=2, long_window=3).tolist() == [1, 1, 0, 0, 0, 0]

    def test_a_window_longer_than_the_data_gives_no_signal_even_for_a_negative_series(self):
        # a spread can be negative: a NaN average was filled with 0, and 0 > a negative average read as a crossover
        assert sma_crossover(-RISING, short_window=100, long_window=3).tolist() == [0] * 6
        assert sma_crossover(-RISING, short_window=3, long_window=100).tolist() == [0] * 6
        assert sma_crossover(RISING, short_window=100, long_window=100).tolist() == [0] * 6

    def test_equal_averages_are_not_a_crossover(self):
        assert sma_crossover(np.full(6, 5.0), short_window=2, long_window=3).tolist() == [0] * 6

    def test_defaults_are_20_and_50(self):
        prices = np.linspace(1, 200, 120)
        assert sma_crossover(prices).tolist() == sma_crossover(prices, 20, 50).tolist()
        assert sma_crossover(prices).tolist() != sma_crossover(prices, 50, 20).tolist()

    def test_returns_ints(self):
        assert sma_crossover(RISING, 2, 3).dtype.kind == "i"

    @pytest.mark.parametrize("name", ["short_window", "long_window"])
    def test_rejects_bad_windows(self, name):
        with pytest.raises(ValueError, match=name):
            sma_crossover(RISING, **{name: 0})
        with pytest.raises(TypeError, match=name):
            sma_crossover(RISING, **{name: 2.5})

    def test_rejects_bad_prices(self):
        with pytest.raises(ValueError):
            sma_crossover(np.array([1.0, np.nan, 3.0]))


class TestPriceAboveSmaValues:
    def test_rising_prices(self):
        assert price_above_sma(RISING, window=3).tolist() == [0, 0, 1, 1, 1, 1]

    def test_falling_prices(self):
        # SMA (3) after back-fill: 5 5 5 4 3 2; only the first price (6) is above it, 5 is not above 5
        assert price_above_sma(FALLING, window=3).tolist() == [1, 0, 0, 0, 0, 0]

    def test_a_price_equal_to_its_average_is_not_above_it(self):
        assert price_above_sma(np.full(5, 7.0), window=3).tolist() == [0] * 5

    def test_default_window_is_50(self):
        prices = np.linspace(1, 100, 80)
        assert price_above_sma(prices).tolist() == price_above_sma(prices, window=50).tolist()
        assert price_above_sma(prices).tolist() != price_above_sma(prices, window=10).tolist()

    def test_a_window_longer_than_the_data_gives_no_signal(self):
        # no average exists: not "above 0" (which every positive price would be)
        assert price_above_sma(RISING, window=100).tolist() == [0] * 6
        assert price_above_sma(RISING, window=7).tolist() == [0] * 6

    def test_rejects_bad_windows(self):
        with pytest.raises(ValueError, match="window"):
            price_above_sma(RISING, window=0)
        with pytest.raises(TypeError, match="window"):
            price_above_sma(RISING, window="3")


class TestRsi:
    def test_rsi_helper_is_neutral_at_the_start_and_100_on_a_pure_rise(self):
        import pandas as pd

        rsi = calculate_rsi(pd.Series(RISING), period=3)
        assert rsi.tolist() == [50.0, 50.0, 100.0, 100.0, 100.0, 100.0]

    def test_rsi_helper_is_0_on_a_pure_fall(self):
        import pandas as pd

        rsi = calculate_rsi(pd.Series(FALLING), period=3)
        assert rsi.tolist() == [50.0, 50.0, 0.0, 0.0, 0.0, 0.0]

    def test_overbought_values(self):
        assert rsi_overbought(RISING, period=3, threshold=70).tolist() == [0, 0, 1, 1, 1, 1]
        assert rsi_overbought(FALLING, period=3, threshold=70).tolist() == [0] * 6

    def test_oversold_values(self):
        assert rsi_oversold(FALLING, period=3, threshold=30).tolist() == [0, 0, 1, 1, 1, 1]
        assert rsi_oversold(RISING, period=3, threshold=30).tolist() == [0] * 6

    def test_overbought_threshold_is_strict(self):
        # RSI is exactly 100 on a pure rise: "> 100" never holds, "> 99.9" does
        assert rsi_overbought(RISING, period=3, threshold=100).tolist() == [0] * 6
        assert rsi_overbought(RISING, period=3, threshold=99.9).tolist() == [0, 0, 1, 1, 1, 1]

    def test_oversold_threshold_is_strict(self):
        assert rsi_oversold(FALLING, period=3, threshold=0).tolist() == [0] * 6
        assert rsi_oversold(FALLING, period=3, threshold=0.1).tolist() == [0, 0, 1, 1, 1, 1]

    def test_flat_prices_are_neutral(self):
        flat = np.full(10, 100.0)
        assert rsi_overbought(flat, period=3, threshold=70).tolist() == [0] * 10
        assert rsi_oversold(flat, period=3, threshold=30).tolist() == [0] * 10

    def test_default_period_is_14_and_thresholds_70_and_30(self):
        prices = np.array([100 * (1.05**i) for i in range(40)])
        assert rsi_overbought(prices).tolist() == rsi_overbought(prices, period=14, threshold=70).tolist()
        assert rsi_overbought(prices).tolist() != rsi_overbought(prices, period=3).tolist()
        falling = prices[::-1].copy()
        assert rsi_oversold(falling).tolist() == rsi_oversold(falling, period=14, threshold=30).tolist()
        assert rsi_oversold(falling).tolist() != rsi_oversold(falling, period=3).tolist()
        # the default thresholds differ from each other and from 50
        wavy = 100 + 5 * np.sin(np.linspace(0, 12, 60))
        assert rsi_overbought(wavy, threshold=70).sum() != rsi_overbought(wavy, threshold=50).sum()
        assert rsi_oversold(wavy, threshold=30).sum() != rsi_oversold(wavy, threshold=50).sum()

    @pytest.mark.parametrize("func", [rsi_overbought, rsi_oversold])
    def test_rejects_bad_arguments(self, func):
        with pytest.raises(ValueError, match="period"):
            func(RISING, period=0)
        with pytest.raises(TypeError, match="period"):
            func(RISING, period=True)
        with pytest.raises(ValueError, match="threshold"):
            func(RISING, threshold=101)
        with pytest.raises(ValueError, match="threshold"):
            func(RISING, threshold=-1)
        with pytest.raises(ValueError, match="threshold"):
            func(RISING, threshold=float("nan"))
        with pytest.raises(TypeError, match="threshold"):
            func(RISING, threshold="70")

    @pytest.mark.parametrize("func", [rsi_overbought, rsi_oversold])
    def test_threshold_bounds_are_accepted(self, func):
        func(RISING, period=3, threshold=0)
        func(RISING, period=3, threshold=100)


class TestBollingerSqueeze:
    def test_constant_prices_squeeze_once_the_window_is_full(self):
        assert bollinger_squeeze(np.full(5, 100.0), window=3, squeeze_threshold=0.1).tolist() == [0, 0, 1, 1, 1]

    def test_the_warm_up_is_never_a_squeeze_whatever_the_threshold(self):
        assert bollinger_squeeze(np.full(5, 100.0), window=3, squeeze_threshold=10).tolist() == [0, 0, 1, 1, 1]

    def test_a_bandwidth_equal_to_the_threshold_is_not_a_squeeze(self):
        # constant prices have bandwidth exactly 0
        assert bollinger_squeeze(np.full(5, 100.0), window=3, squeeze_threshold=0.0).tolist() == [0] * 5

    def test_wide_bands_are_not_a_squeeze(self):
        prices = np.array([100.0, 130.0, 100.0, 130.0, 100.0, 130.0])
        assert bollinger_squeeze(prices, window=3).tolist() == [0] * 6

    def test_the_threshold_is_strict_and_the_default_is_0_05(self):
        # std (window 2) of [100, 101] is 0.7071; bandwidth = 4 * std / 100.5 = 0.02814 for num_std 2
        prices = np.array([100.0, 101.0, 100.0, 101.0])
        assert bollinger_squeeze(prices, window=2, squeeze_threshold=0.03).tolist() == [0, 1, 1, 1]
        assert bollinger_squeeze(prices, window=2, squeeze_threshold=0.0281).tolist() == [0, 0, 0, 0]
        assert bollinger_squeeze(prices, window=2).tolist() == [0, 1, 1, 1]  # default threshold 0.05
        assert bollinger_squeeze(prices, window=2, squeeze_threshold=0.0).tolist() == [0, 0, 0, 0]

    def test_num_std_widens_the_bands(self):
        prices = np.array([100.0, 101.0, 100.0, 101.0])
        assert bollinger_squeeze(prices, window=2, num_std=2.0).tolist() == [0, 1, 1, 1]
        assert bollinger_squeeze(prices, window=2, num_std=4.0).tolist() == [0, 0, 0, 0]
        assert bollinger_squeeze(prices, window=2, num_std=0).tolist() == [0, 1, 1, 1]

    def test_default_window_is_20(self):
        prices = np.full(40, 100.0)
        regime = bollinger_squeeze(prices)
        assert regime[:19].sum() == 0
        assert regime[19:].tolist() == [1] * 21

    def test_a_spread_with_a_negative_average_is_not_a_false_squeeze(self):
        # Bandwidth is divided by |SMA|; divided by a negative SMA it was negative, and "negative < threshold" read as a squeeze.
        spread = np.array([-10.0, -30.0, -10.0, -30.0, -10.0])
        assert bollinger_squeeze(spread, window=3).tolist() == [0, 0, 0, 0, 0]

    def test_a_series_that_averages_zero_is_not_a_squeeze(self):
        assert bollinger_squeeze(np.zeros(6), window=3).tolist() == [0] * 6

    def test_rejects_bad_arguments(self):
        prices = np.full(10, 100.0)
        with pytest.raises(ValueError, match="window"):
            bollinger_squeeze(prices, window=1)
        with pytest.raises(TypeError, match="window"):
            bollinger_squeeze(prices, window=2.0)
        with pytest.raises(ValueError, match="num_std"):
            bollinger_squeeze(prices, num_std=-1)
        with pytest.raises(ValueError, match="squeeze_threshold"):
            bollinger_squeeze(prices, squeeze_threshold=-0.1)
        with pytest.raises(ValueError, match="squeeze_threshold"):
            bollinger_squeeze(prices, squeeze_threshold=float("inf"))


class TestAtrExpansion:
    def test_constant_prices_never_expand(self):
        assert atr_expansion(np.full(60, 100.0), window=5).tolist() == [0] * 60

    def test_volatility_that_starts_after_a_calm_spell_is_an_expansion(self):
        prices = np.concatenate([np.full(40, 100.0), np.tile([100.0, 120.0], 10)])
        regime = atr_expansion(prices, window=5)
        assert regime[:41].sum() == 0  # calm: volatility 0 is not above its average 0
        assert regime[41:].sum() > 0

    def test_volatility_that_fades_is_not_an_expansion(self):
        prices = np.concatenate([np.tile([100.0, 120.0], 20), np.full(30, 100.0)])
        regime = atr_expansion(prices, window=5)
        assert regime[-10:].sum() == 0

    def test_default_window_is_14(self):
        prices = np.concatenate([np.full(60, 100.0), np.tile([100.0, 110.0], 30)])
        assert atr_expansion(prices).tolist() == atr_expansion(prices, window=14).tolist()
        assert atr_expansion(prices).tolist() != atr_expansion(prices, window=5).tolist()

    def test_rejects_bad_windows(self):
        with pytest.raises(ValueError, match="window"):
            atr_expansion(RISING, window=1)
        with pytest.raises(TypeError, match="window"):
            atr_expansion(RISING, window=1.5)
