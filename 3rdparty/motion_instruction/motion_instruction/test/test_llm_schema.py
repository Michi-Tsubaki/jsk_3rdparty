import pytest
from pydantic import ValidationError

from motion_instruction.models.llm_schema import LLMParsedCommand, LLMMotionSegment


def valid_segment(**overrides):
    data = {
        "kind": "translation",
        "direction": "left",
        "axis": "unspecified",
        "has_numeric_value": True,
        "value": 5.0,
        "unit": "cm",
        "qualifier": "none",
        "target_object_id": "",
        "source_text": "left 5cm",
        "preserve_orientation": True,
    }
    data.update(overrides)
    return data


def valid_command(**overrides):
    data = {
        "schema_version": "1.0",
        "end_effector": "",
        "frame_id": "",
        "segments": [valid_segment()],
        "has_duration": False,
        "duration_value": 0.0,
        "duration_unit": "none",
        "duration_scope": "unspecified",
        "ambiguous": False,
        "ambiguity_reasons": [],
        "clarification_question": "",
    }
    data.update(overrides)
    return data


def test_valid_translation_schema():
    command = LLMParsedCommand(**valid_command())
    assert command.segments[0].kind == "translation"


def test_extra_field_is_rejected():
    data = valid_segment(extra_field="bad")
    with pytest.raises(ValidationError):
        LLMMotionSegment(**data)


def test_unknown_enum_is_rejected():
    data = valid_segment(direction="diagonal")
    with pytest.raises(ValidationError):
        LLMMotionSegment(**data)


def test_empty_segments_allowed_at_schema_layer_for_ambiguous_command():
    command = LLMParsedCommand(
        **valid_command(
            segments=[],
            ambiguous=True,
            ambiguity_reasons=["unsupported_or_non_motion_utterance"],
            clarification_question="clarify",
        )
    )
    assert command.segments == []
