import math

import pytest

from motion_instruction.guard.unit_converter import angle_to_rad, duration_to_ms, length_to_m
from motion_instruction.models.errors import GuardError


def test_length_units():
    assert length_to_m(5, "mm") == pytest.approx(0.005)
    assert length_to_m(5, "cm") == pytest.approx(0.05)
    assert length_to_m(5, "m") == pytest.approx(5.0)


def test_angle_units():
    assert angle_to_rad(180, "deg") == pytest.approx(math.pi)
    assert angle_to_rad(0.2, "rad") == pytest.approx(0.2)


def test_duration_units():
    assert duration_to_ms(1, "s") == 1000
    assert duration_to_ms(250, "ms") == 250


@pytest.mark.parametrize("value", [0.0, -1.0, math.inf, math.nan])
def test_invalid_values_rejected(value):
    with pytest.raises(GuardError):
        length_to_m(value, "cm")
