from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


DOMAIN_SCHEMA_VERSION = "1.0"

SegmentKind = Literal[
    "translation",
    "rotation",
    "semantic_translation",
    "semantic_rotation",
]
ResolvedKind = Literal["translation", "rotation"]


@dataclass(frozen=True)
class DomainSegment:
    kind: SegmentKind
    direction: str
    axis: str
    value_si: float
    has_numeric_value: bool
    qualifier: str
    target_object_id: str
    source_text: str
    preserve_orientation: bool
    duration_ms: int


@dataclass(frozen=True)
class DomainParsedCommand:
    command_id: str
    original_text: str
    provider: str
    model: str
    end_effector: str
    frame_id: str
    segments: tuple[DomainSegment, ...]


@dataclass(frozen=True)
class ResolvedMotionSegment:
    kind: ResolvedKind
    frame_id: str
    translation_m: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation_axis: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation_angle_rad: float = 0.0
    duration_ms: int = 5000
    source_text: str = ""


@dataclass(frozen=True)
class GuardConfig:
    default_frame_id: str = "base_link"
    execution_frame_id: str = "base_link"
    default_end_effector: str = "right_hand"
    default_translation_direction: str = "forward"
    default_translation_axis: str = "x"
    default_translation_axis_direction: str = "positive"
    default_translation_m: float = 0.010
    default_rotation_axis: str = "z"
    default_rotation_direction: str = "positive"
    default_rotation_rad: float = 0.17453292519943295
    allowed_frames: tuple[str, ...] = ("base_link", "torso_link", "right_tool", "left_tool")
    max_segments: int = 8
    max_translation_per_segment_m: float = 0.10
    max_translation_total_m: float = 0.20
    max_rotation_per_segment_rad: float = 0.78539816339
    max_rotation_total_rad: float = 1.57079632679
    default_segment_duration_ms: int = 5000
    min_segment_duration_ms: int = 200
    max_segment_duration_ms: int = 30000
    enable_qualitative_translation: bool = False
    enable_qualitative_rotation: bool = False
    qualitative_translation_m: dict[str, float] = field(
        default_factory=lambda: {
            "tiny": 0.002,
            "small": 0.010,
            "medium": 0.030,
            "large": 0.050,
        }
    )
    qualitative_rotation_rad: dict[str, float] = field(
        default_factory=lambda: {
            "tiny": 0.0174533,
            "small": 0.0872665,
            "medium": 0.174533,
            "large": 0.349066,
        }
    )


def duration_ms_to_seconds_nanoseconds(duration_ms: int) -> tuple[int, int]:
    seconds = duration_ms // 1000
    nanoseconds = (duration_ms % 1000) * 1_000_000
    return seconds, nanoseconds
