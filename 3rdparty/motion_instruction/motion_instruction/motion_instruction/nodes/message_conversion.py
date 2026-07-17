from __future__ import annotations

from geometry_msgs.msg import Vector3

from motion_instruction.models.domain import ResolvedMotionSegment, duration_ms_to_seconds_nanoseconds
from motion_instruction.models.llm_schema import LLMParsedCommand
from motion_instruction_interfaces.msg import ParsedCommand, ParsedSegment
from motion_instruction_interfaces.msg import ResolvedMotionSegment as ResolvedMotionSegmentMsg


_PARSED_KIND_TO_MSG = {
    "translation": ParsedSegment.TRANSLATION,
    "rotation": ParsedSegment.ROTATION,
    "semantic_translation": ParsedSegment.SEMANTIC_TRANSLATION,
    "semantic_rotation": ParsedSegment.SEMANTIC_ROTATION,
}

_RESOLVED_KIND_TO_MSG = {
    "translation": ResolvedMotionSegmentMsg.TRANSLATION,
    "rotation": ResolvedMotionSegmentMsg.ROTATION,
}

_MSG_KIND_TO_RESOLVED = {
    ResolvedMotionSegmentMsg.TRANSLATION: "translation",
    ResolvedMotionSegmentMsg.ROTATION: "rotation",
}


def parsed_command_to_msg(
    command: LLMParsedCommand,
    *,
    command_id: str,
    original_text: str,
    provider: str,
    model: str,
) -> ParsedCommand:
    message = ParsedCommand()
    message.command_id = command_id
    message.original_text = original_text
    message.provider = provider
    message.model = model
    message.end_effector = command.end_effector
    message.frame_id = command.frame_id
    message.has_duration = command.has_duration
    message.duration_value = command.duration_value
    message.duration_unit = command.duration_unit
    message.duration_scope = command.duration_scope
    message.ambiguous = command.ambiguous
    message.ambiguity_reasons = list(command.ambiguity_reasons)
    message.clarification_question = command.clarification_question
    for segment in command.segments:
        segment_msg = ParsedSegment()
        segment_msg.kind = _PARSED_KIND_TO_MSG[segment.kind]
        segment_msg.direction = segment.direction
        segment_msg.axis = segment.axis
        segment_msg.has_numeric_value = segment.has_numeric_value
        segment_msg.value = segment.value
        segment_msg.unit = segment.unit
        segment_msg.qualifier = segment.qualifier
        segment_msg.target_object_id = segment.target_object_id
        segment_msg.source_text = segment.source_text
        segment_msg.preserve_orientation = segment.preserve_orientation
        message.segments.append(segment_msg)
    return message


def resolved_segment_to_msg(segment: ResolvedMotionSegment) -> ResolvedMotionSegmentMsg:
    message = ResolvedMotionSegmentMsg()
    message.kind = _RESOLVED_KIND_TO_MSG[segment.kind]
    message.frame_id = segment.frame_id
    message.translation_m = Vector3(
        x=segment.translation_m[0],
        y=segment.translation_m[1],
        z=segment.translation_m[2],
    )
    message.rotation_axis = Vector3(
        x=segment.rotation_axis[0],
        y=segment.rotation_axis[1],
        z=segment.rotation_axis[2],
    )
    message.rotation_angle_rad = segment.rotation_angle_rad
    seconds, nanoseconds = duration_ms_to_seconds_nanoseconds(segment.duration_ms)
    message.duration.sec = seconds
    message.duration.nanosec = nanoseconds
    message.source_text = segment.source_text
    return message


def resolved_segment_from_msg(message: ResolvedMotionSegmentMsg) -> ResolvedMotionSegment:
    duration_ms = message.duration.sec * 1000 + int(round(message.duration.nanosec / 1_000_000))
    return ResolvedMotionSegment(
        kind=_MSG_KIND_TO_RESOLVED[message.kind],
        frame_id=message.frame_id,
        translation_m=(message.translation_m.x, message.translation_m.y, message.translation_m.z),
        rotation_axis=(message.rotation_axis.x, message.rotation_axis.y, message.rotation_axis.z),
        rotation_angle_rad=message.rotation_angle_rad,
        duration_ms=duration_ms,
        source_text=message.source_text,
    )
