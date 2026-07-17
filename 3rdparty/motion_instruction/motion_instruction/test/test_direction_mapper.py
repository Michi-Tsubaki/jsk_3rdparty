import pytest

from motion_instruction.guard.direction_mapper import rotation_axis, translation_vector
from motion_instruction.models.errors import ResolverError


def test_rep103_translation_words():
    assert translation_vector("forward", "unspecified", 0.1) == pytest.approx((0.1, 0.0, 0.0))
    assert translation_vector("backward", "unspecified", 0.1) == pytest.approx((-0.1, 0.0, 0.0))
    assert translation_vector("left", "unspecified", 0.1) == pytest.approx((0.0, 0.1, 0.0))
    assert translation_vector("right", "unspecified", 0.1) == pytest.approx((0.0, -0.1, 0.0))
    assert translation_vector("up", "unspecified", 0.1) == pytest.approx((0.0, 0.0, 0.1))
    assert translation_vector("down", "unspecified", 0.1) == pytest.approx((0.0, 0.0, -0.1))


def test_axis_positive_negative_translation():
    assert translation_vector("positive", "x", 0.1) == pytest.approx((0.1, 0.0, 0.0))
    assert translation_vector("negative", "z", 0.1) == pytest.approx((0.0, 0.0, -0.1))


def test_rotation_axis_right_hand_rule():
    assert rotation_axis("positive", "z") == pytest.approx((0.0, 0.0, 1.0))
    assert rotation_axis("negative", "x") == pytest.approx((-1.0, 0.0, 0.0))
    assert rotation_axis("counterclockwise", "z") == pytest.approx((0.0, 0.0, 1.0))
    assert rotation_axis("clockwise", "z") == pytest.approx((0.0, 0.0, -1.0))


def test_ambiguous_rotation_rejected():
    with pytest.raises(ResolverError):
        rotation_axis("clockwise", "unspecified")
