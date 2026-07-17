import math

import pytest

from motion_instruction.guard import CommandGuard
from motion_instruction.models import GuardConfig
from motion_instruction.models.errors import GuardError
from motion_instruction.models.llm_schema import LLMParsedCommand
from motion_instruction.resolver import RelativeCartesianResolver


def command_with_segments(segments, **overrides):
    data = {
        "schema_version": "1.0",
        "end_effector": "",
        "frame_id": "",
        "segments": segments,
        "has_duration": False,
        "duration_value": 0.0,
        "duration_unit": "none",
        "duration_scope": "unspecified",
        "ambiguous": False,
        "ambiguity_reasons": [],
        "clarification_question": "",
    }
    data.update(overrides)
    return LLMParsedCommand(**data)


def translation(direction, value, unit="cm"):
    return {
        "kind": "translation",
        "direction": direction,
        "axis": "unspecified",
        "has_numeric_value": True,
        "value": value,
        "unit": unit,
        "qualifier": "none",
        "target_object_id": "",
        "source_text": f"{direction} {value}{unit}",
        "preserve_orientation": True,
    }


def translation_without_value(direction="unspecified", axis="unspecified"):
    return {
        "kind": "translation",
        "direction": direction,
        "axis": axis,
        "has_numeric_value": False,
        "value": 0.0,
        "unit": "none",
        "qualifier": "none",
        "target_object_id": "",
        "source_text": "move",
        "preserve_orientation": True,
    }


def rotation(axis="z", direction="positive", value=10.0, unit="deg"):
    return {
        "kind": "rotation",
        "direction": direction,
        "axis": axis,
        "has_numeric_value": True,
        "value": value,
        "unit": unit,
        "qualifier": "none",
        "target_object_id": "",
        "source_text": f"{axis} {direction} {value}{unit}",
        "preserve_orientation": False,
    }


def rotation_without_value(axis="unspecified", direction="unspecified"):
    return {
        "kind": "rotation",
        "direction": direction,
        "axis": axis,
        "has_numeric_value": False,
        "value": 0.0,
        "unit": "none",
        "qualifier": "none",
        "target_object_id": "",
        "source_text": "rotate",
        "preserve_orientation": False,
    }


def test_ac01_ordered_translation_is_not_collapsed():
    parsed = command_with_segments(
        [
            translation("left", 5),
            translation("right", 4),
            translation("up", 2),
        ]
    )
    domain = CommandGuard().validate(
        parsed,
        original_text="left/right/up",
        provider="mock",
        model="mock",
        command_id="cmd",
    )
    resolved = RelativeCartesianResolver().resolve(domain)

    assert len(resolved) == 3
    assert [segment.translation_m for segment in resolved] == pytest.approx(
        [(0.0, 0.05, 0.0), (0.0, -0.04, 0.0), (0.0, 0.0, 0.02)]
    )
    assert [segment.duration_ms for segment in resolved] == [5000, 5000, 5000]


def test_ac02_numeric_rotation():
    parsed = command_with_segments([rotation()])
    domain = CommandGuard().validate(
        parsed,
        original_text="z positive 10deg",
        provider="mock",
        model="mock",
        command_id="cmd",
    )
    resolved = RelativeCartesianResolver().resolve(domain)
    assert resolved[0].rotation_axis == pytest.approx((0.0, 0.0, 1.0))
    assert resolved[0].rotation_angle_rad == pytest.approx(math.pi / 18.0)


def test_ac03_explicit_duration():
    parsed = command_with_segments(
        [translation("up", 1)],
        has_duration=True,
        duration_value=1.0,
        duration_unit="s",
        duration_scope="per_segment",
    )
    domain = CommandGuard().validate(
        parsed,
        original_text="up 1cm in 1s",
        provider="mock",
        model="mock",
        command_id="cmd",
    )
    assert domain.segments[0].duration_ms == 1000


def test_ac09_limit_exceeded_is_rejected_without_clamp():
    parsed = command_with_segments([translation("left", 5, unit="m")])
    with pytest.raises(GuardError) as exc:
        CommandGuard().validate(parsed, original_text="left 5m", provider="mock", model="mock")
    assert exc.value.code == "LIMIT_EXCEEDED"


def test_total_duration_for_multiple_segments_rejected():
    parsed = command_with_segments(
        [translation("left", 1), translation("right", 1)],
        has_duration=True,
        duration_value=3.0,
        duration_unit="s",
        duration_scope="total",
    )
    with pytest.raises(GuardError) as exc:
        CommandGuard().validate(parsed, original_text="multi", provider="mock", model="mock")
    assert exc.value.code == "UNSUPPORTED_DURATION_SCOPE"


def test_frame_whitelist():
    parsed = command_with_segments([translation("left", 1)], frame_id="map")
    with pytest.raises(GuardError) as exc:
        CommandGuard().validate(parsed, original_text="left", provider="mock", model="mock")
    assert exc.value.code == "FRAME_NOT_ALLOWED"


def test_ac10_ambiguous_command_rejected():
    parsed = command_with_segments(
        [],
        ambiguous=True,
        ambiguity_reasons=["rotation_axis_unspecified"],
        clarification_question="axis?",
    )
    with pytest.raises(GuardError) as exc:
        CommandGuard().validate(parsed, original_text="right little rotate", provider="mock", model="mock")
    assert exc.value.code == "AMBIGUOUS_COMMAND"


def test_ambiguous_flag_with_segments_uses_defaults():
    parsed = command_with_segments(
        [translation_without_value()],
        ambiguous=True,
        ambiguity_reasons=["direction_unspecified", "length_unspecified"],
        clarification_question="direction?",
    )
    domain = CommandGuard().validate(parsed, original_text="move", provider="mock", model="mock")
    resolved = RelativeCartesianResolver().resolve(domain)

    assert domain.end_effector == "right_hand"
    assert domain.frame_id == "base_link"
    assert domain.segments[0].direction == "forward"
    assert domain.segments[0].axis == "unspecified"
    assert domain.segments[0].value_si == pytest.approx(0.010)
    assert resolved[0].translation_m == pytest.approx((0.010, 0.0, 0.0))


def test_axis_translation_without_sign_uses_default_positive():
    parsed = command_with_segments([translation_without_value(axis="y")])
    domain = CommandGuard().validate(parsed, original_text="y move", provider="mock", model="mock")
    resolved = RelativeCartesianResolver().resolve(domain)

    assert domain.segments[0].direction == "positive"
    assert domain.segments[0].axis == "y"
    assert resolved[0].translation_m == pytest.approx((0.0, 0.010, 0.0))


def test_rotation_missing_axis_direction_and_value_uses_defaults():
    parsed = command_with_segments([rotation_without_value()])
    domain = CommandGuard(GuardConfig(max_rotation_per_segment_rad=10.0)).validate(
        parsed,
        original_text="rotate",
        provider="mock",
        model="mock",
    )
    resolved = RelativeCartesianResolver().resolve(domain)

    assert domain.segments[0].direction == "positive"
    assert domain.segments[0].axis == "z"
    assert domain.segments[0].value_si == pytest.approx(0.17453292519943295)
    assert resolved[0].rotation_axis == pytest.approx((0.0, 0.0, 1.0))
