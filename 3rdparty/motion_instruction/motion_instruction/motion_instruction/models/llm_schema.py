from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator


SegmentKind = Literal[
    "translation",
    "rotation",
    "semantic_translation",
    "semantic_rotation",
]
Direction = Literal[
    "forward",
    "backward",
    "left",
    "right",
    "up",
    "down",
    "positive",
    "negative",
    "clockwise",
    "counterclockwise",
    "away_from_object",
    "toward_object",
    "unspecified",
]
Axis = Literal["x", "y", "z", "unspecified"]
Unit = Literal["mm", "cm", "m", "deg", "rad", "none"]
Qualifier = Literal["none", "tiny", "small", "medium", "large"]
DurationUnit = Literal["ms", "s", "none"]
DurationScope = Literal["per_segment", "total", "unspecified"]


class LLMMotionSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: SegmentKind
    direction: Direction
    axis: Axis
    has_numeric_value: bool
    value: float
    unit: Unit
    qualifier: Qualifier
    target_object_id: str
    source_text: str
    preserve_orientation: bool


class LLMParsedCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"]
    end_effector: str
    frame_id: str
    segments: list[LLMMotionSegment]

    has_duration: bool
    duration_value: float
    duration_unit: DurationUnit
    duration_scope: DurationScope

    ambiguous: bool
    ambiguity_reasons: list[str]
    clarification_question: str

    @field_validator("ambiguity_reasons")
    @classmethod
    def _reject_empty_reason_items(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("ambiguity_reasons must not contain empty items")
        return value
