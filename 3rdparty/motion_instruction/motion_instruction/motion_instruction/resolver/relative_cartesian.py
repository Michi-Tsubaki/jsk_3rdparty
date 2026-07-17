from motion_instruction.guard.direction_mapper import rotation_axis, translation_vector
from motion_instruction.models.domain import DomainParsedCommand, ResolvedMotionSegment
from motion_instruction.models.errors import ResolverError


class RelativeCartesianResolver:
    def supports(self, command: DomainParsedCommand) -> bool:
        return all(segment.kind in ("translation", "rotation") for segment in command.segments)

    def resolve(self, command: DomainParsedCommand) -> list[ResolvedMotionSegment]:
        if not self.supports(command):
            raise ResolverError("UNSUPPORTED_INTENT", "only numeric translation/rotation is supported")

        resolved: list[ResolvedMotionSegment] = []
        for segment in command.segments:
            if segment.kind == "translation":
                resolved.append(
                    ResolvedMotionSegment(
                        kind="translation",
                        frame_id=command.frame_id,
                        translation_m=translation_vector(
                            segment.direction,
                            segment.axis,
                            segment.value_si,
                        ),
                        duration_ms=segment.duration_ms,
                        source_text=segment.source_text,
                    )
                )
            elif segment.kind == "rotation":
                resolved.append(
                    ResolvedMotionSegment(
                        kind="rotation",
                        frame_id=command.frame_id,
                        rotation_axis=rotation_axis(segment.direction, segment.axis),
                        rotation_angle_rad=segment.value_si,
                        duration_ms=segment.duration_ms,
                        source_text=segment.source_text,
                    )
                )
        return resolved
