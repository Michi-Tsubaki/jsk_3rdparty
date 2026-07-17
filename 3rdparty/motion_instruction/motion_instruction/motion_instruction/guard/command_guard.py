from __future__ import annotations

import uuid

from motion_instruction.guard.unit_converter import angle_to_rad, duration_to_ms, length_to_m
from motion_instruction.models.domain import DomainParsedCommand, DomainSegment, GuardConfig
from motion_instruction.models.errors import GuardError
from motion_instruction.models.llm_schema import LLMParsedCommand, LLMMotionSegment


_AXES = {"x", "y", "z"}
_AXIS_DIRECTIONS = {"positive", "negative"}


class CommandGuard:
    def __init__(self, config: GuardConfig | None = None) -> None:
        self.config = config or GuardConfig()

    def validate(
        self,
        command: LLMParsedCommand,
        *,
        original_text: str,
        provider: str,
        model: str,
        command_id: str | None = None,
    ) -> DomainParsedCommand:
        if command.ambiguous and not command.segments:
            message = command.clarification_question or "; ".join(command.ambiguity_reasons)
            raise GuardError("AMBIGUOUS_COMMAND", message or "command is ambiguous")
        if not command.segments:
            raise GuardError("UNSUPPORTED_INTENT", "command does not contain motion segments")
        if len(command.segments) > self.config.max_segments:
            raise GuardError(
                "LIMIT_EXCEEDED",
                f"segment count {len(command.segments)} exceeds {self.config.max_segments}",
            )

        frame_id = command.frame_id.strip() or self.config.default_frame_id
        if not frame_id:
            raise GuardError("AMBIGUOUS_COMMAND", "frame_id is not specified")
        if frame_id not in self.config.allowed_frames:
            raise GuardError("FRAME_NOT_ALLOWED", f"frame is not allowed: {frame_id}")

        end_effector = command.end_effector.strip() or self.config.default_end_effector
        if not end_effector:
            raise GuardError("AMBIGUOUS_COMMAND", "end_effector is not specified")

        duration_ms = self._duration_ms(command)
        segments = tuple(self._validate_segment(segment, duration_ms) for segment in command.segments)
        self._validate_totals(segments)

        return DomainParsedCommand(
            command_id=command_id or str(uuid.uuid4()),
            original_text=original_text,
            provider=provider,
            model=model,
            end_effector=end_effector,
            frame_id=frame_id,
            segments=segments,
        )

    def _duration_ms(self, command: LLMParsedCommand) -> int:
        if not command.has_duration:
            duration_ms = self.config.default_segment_duration_ms
        else:
            if command.duration_scope == "total" and len(command.segments) > 1:
                raise GuardError(
                    "UNSUPPORTED_DURATION_SCOPE",
                    "total duration for multiple segments is not supported",
                )
            if command.duration_unit == "none":
                raise GuardError("INVALID_SCHEMA", "duration unit is none while has_duration is true")
            duration_ms = duration_to_ms(command.duration_value, command.duration_unit)
        if not self.config.min_segment_duration_ms <= duration_ms <= self.config.max_segment_duration_ms:
            raise GuardError(
                "LIMIT_EXCEEDED",
                (
                    f"duration {duration_ms} ms is outside "
                    f"{self.config.min_segment_duration_ms}..{self.config.max_segment_duration_ms} ms"
                ),
            )
        return duration_ms

    def _validate_segment(self, segment: LLMMotionSegment, duration_ms: int) -> DomainSegment:
        if segment.kind == "translation":
            direction, axis = self._translation_direction_axis(segment)
            value_si = self._translation_value(segment)
        elif segment.kind == "rotation":
            direction, axis = self._rotation_direction_axis(segment)
            value_si = self._rotation_value(segment)
        elif segment.kind == "semantic_translation":
            raise GuardError("UNSUPPORTED_INTENT", "semantic translation is not implemented")
        elif segment.kind == "semantic_rotation":
            raise GuardError("UNSUPPORTED_INTENT", "semantic rotation is not implemented")
        else:
            raise GuardError("INVALID_SCHEMA", f"unknown segment kind: {segment.kind}")

        return DomainSegment(
            kind=segment.kind,
            direction=direction,
            axis=axis,
            value_si=value_si,
            has_numeric_value=segment.has_numeric_value,
            qualifier=segment.qualifier,
            target_object_id=segment.target_object_id,
            source_text=segment.source_text,
            preserve_orientation=segment.preserve_orientation,
            duration_ms=duration_ms,
        )

    def _translation_direction_axis(self, segment: LLMMotionSegment) -> tuple[str, str]:
        direction = segment.direction
        axis = segment.axis
        if direction == "unspecified":
            if axis in _AXES:
                direction = self.config.default_translation_axis_direction
            else:
                direction = self.config.default_translation_direction
                axis = "unspecified"
        elif direction in _AXIS_DIRECTIONS and axis == "unspecified":
            axis = self.config.default_translation_axis
        return direction, axis

    def _rotation_direction_axis(self, segment: LLMMotionSegment) -> tuple[str, str]:
        direction = segment.direction
        axis = segment.axis
        if direction == "unspecified":
            direction = self.config.default_rotation_direction
        if axis == "unspecified":
            axis = self.config.default_rotation_axis
        return direction, axis

    def _translation_value(self, segment: LLMMotionSegment) -> float:
        if segment.has_numeric_value:
            if segment.unit not in ("mm", "cm", "m"):
                raise GuardError("INVALID_SCHEMA", f"translation unit must be length, got {segment.unit}")
            value_m = length_to_m(segment.value, segment.unit)
        elif segment.qualifier != "none" and self.config.enable_qualitative_translation:
            value_m = self.config.qualitative_translation_m[segment.qualifier]
        else:
            value_m = self.config.default_translation_m
        if value_m > self.config.max_translation_per_segment_m:
            raise GuardError(
                "LIMIT_EXCEEDED",
                (
                    f"translation {value_m:.6g} m exceeds per-segment limit "
                    f"{self.config.max_translation_per_segment_m:.6g} m"
                ),
            )
        return value_m

    def _rotation_value(self, segment: LLMMotionSegment) -> float:
        if segment.has_numeric_value:
            if segment.unit not in ("deg", "rad"):
                raise GuardError("INVALID_SCHEMA", f"rotation unit must be angle, got {segment.unit}")
            value_rad = angle_to_rad(segment.value, segment.unit)
        elif segment.qualifier != "none" and self.config.enable_qualitative_rotation:
            value_rad = self.config.qualitative_rotation_rad[segment.qualifier]
        else:
            value_rad = self.config.default_rotation_rad
        if value_rad > self.config.max_rotation_per_segment_rad:
            raise GuardError(
                "LIMIT_EXCEEDED",
                (
                    f"rotation {value_rad:.6g} rad exceeds per-segment limit "
                    f"{self.config.max_rotation_per_segment_rad:.6g} rad"
                ),
            )
        return value_rad

    def _validate_totals(self, segments: tuple[DomainSegment, ...]) -> None:
        total_translation = sum(segment.value_si for segment in segments if segment.kind == "translation")
        total_rotation = sum(segment.value_si for segment in segments if segment.kind == "rotation")
        if total_translation > self.config.max_translation_total_m:
            raise GuardError(
                "LIMIT_EXCEEDED",
                (
                    f"total translation {total_translation:.6g} m exceeds "
                    f"{self.config.max_translation_total_m:.6g} m"
                ),
            )
        if total_rotation > self.config.max_rotation_total_rad:
            raise GuardError(
                "LIMIT_EXCEEDED",
                (
                    f"total rotation {total_rotation:.6g} rad exceeds "
                    f"{self.config.max_rotation_total_rad:.6g} rad"
                ),
            )
