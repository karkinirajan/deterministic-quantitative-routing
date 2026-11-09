import math

import numpy as np
import pytest

from src.library.core import check_number, check_window, validate_input, validate_output


class TestValidateInput:
    def test_accepts_floats_and_integers(self):
        validate_input(np.array([1.0, 2.0]))
        validate_input(np.array([1, 2, 3]))

    @pytest.mark.parametrize("bad", [[1.0, 2.0], (1.0, 2.0), None, "ab", 5])
    def test_rejects_non_arrays(self, bad):
        with pytest.raises(TypeError, match="numpy array"):
            validate_input(bad)

    def test_rejects_two_dimensions(self):
        with pytest.raises(ValueError, match="1D"):
            validate_input(np.ones((2, 2)))

    @pytest.mark.parametrize("dtype", [bool, str, object])
    def test_rejects_non_numeric_dtypes(self, dtype):
        with pytest.raises(TypeError, match="numeric"):
            validate_input(np.array([1, 0], dtype=dtype))

    @pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
    def test_rejects_nan_and_inf(self, bad):
        with pytest.raises(ValueError, match="NaN or Inf"):
            validate_input(np.array([1.0, bad, 3.0]))

    def test_needs_two_points(self):
        with pytest.raises(ValueError, match="at least 2"):
            validate_input(np.array([1.0]))
        with pytest.raises(ValueError, match="at least 2"):
            validate_input(np.array([]))
        validate_input(np.array([1.0, 1.0]))


class TestValidateOutput:
    def test_accepts_binary_of_the_right_length(self):
        validate_output(np.array([0, 1, 1]), 3)
        validate_output(np.array([0.0, 1.0]), 2)

    def test_rejects_non_arrays(self):
        with pytest.raises(TypeError, match="numpy array"):
            validate_output([0, 1], 2)

    def test_rejects_two_dimensions(self):
        with pytest.raises(ValueError, match="1D"):
            validate_output(np.zeros((2, 2)), 2)

    def test_rejects_a_wrong_length(self):
        with pytest.raises(ValueError, match=r"length \(2\) does not match input length \(3\)"):
            validate_output(np.array([0, 1]), 3)

    @pytest.mark.parametrize("bad", [[0, 2], [0, -1], [0.5, 1], [0, np.nan]])
    def test_rejects_non_binary_values(self, bad):
        with pytest.raises(ValueError, match="binary"):
            validate_output(np.array(bad), 2)


class TestCheckWindow:
    def test_returns_the_value_as_an_int(self):
        assert check_window("w", 5) == 5
        result = check_window("w", np.int64(7))
        assert result == 7 and type(result) is int

    def test_the_minimum_is_inclusive(self):
        assert check_window("w", 1) == 1
        assert check_window("w", 2, minimum=2) == 2
        with pytest.raises(ValueError, match="at least 2, got 1"):
            check_window("w", 1, minimum=2)

    @pytest.mark.parametrize("bad", [0, -3])
    def test_rejects_zero_and_negative(self, bad):
        with pytest.raises(ValueError, match="at least 1"):
            check_window("w", bad)

    @pytest.mark.parametrize("bad", [True, False, 2.0, "3", None, [3]])
    def test_rejects_other_types_including_bool(self, bad):
        with pytest.raises(TypeError, match="w must be an integer"):
            check_window("w", bad)

    def test_the_message_names_the_argument(self):
        with pytest.raises(ValueError, match="short_window"):
            check_window("short_window", 0)


class TestCheckNumber:
    def test_returns_a_float(self):
        result = check_number("x", 3)
        assert result == 3.0 and type(result) is float
        assert check_number("x", np.float64(2.5)) == 2.5
        assert check_number("x", np.int32(2)) == 2.0

    def test_bounds_are_inclusive(self):
        assert check_number("x", 0, 0, 100) == 0.0
        assert check_number("x", 100, 0, 100) == 100.0
        with pytest.raises(ValueError, match="at least 0, got -0.1"):
            check_number("x", -0.1, 0, 100)
        with pytest.raises(ValueError, match="at most 100, got 100.1"):
            check_number("x", 100.1, 0, 100)

    def test_no_bounds_means_any_finite_number(self):
        assert check_number("x", -1e9) == -1e9
        assert check_number("x", 1e9) == 1e9

    def test_only_a_minimum_or_only_a_maximum(self):
        assert check_number("x", 1e9, minimum=0) == 1e9
        assert check_number("x", -1e9, maximum=0) == -1e9

    @pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
    def test_rejects_non_finite(self, bad):
        with pytest.raises(ValueError, match="finite"):
            check_number("x", bad)

    @pytest.mark.parametrize("bad", [True, "5", None, [1], 1 + 2j])
    def test_rejects_other_types_including_bool(self, bad):
        with pytest.raises(TypeError, match="x must be a number"):
            check_number("x", bad)
