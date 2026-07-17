from dataclasses import dataclass

from motion_instruction.models.domain import ResolvedMotionSegment
from motion_instruction.models.errors import GuardError


@dataclass(frozen=True)
class WorkspaceAABB:
    min_x: float
    max_x: float
    min_y: float
    max_y: float
    min_z: float
    max_z: float

    def contains(self, point: tuple[float, float, float]) -> bool:
        x, y, z = point
        return (
            self.min_x <= x <= self.max_x
            and self.min_y <= y <= self.max_y
            and self.min_z <= z <= self.max_z
        )


def check_workspace_path(
    initial_position_m: tuple[float, float, float],
    segments: list[ResolvedMotionSegment],
    workspace: WorkspaceAABB,
) -> None:
    current = initial_position_m
    for index, segment in enumerate(segments, start=1):
        if segment.kind != "translation":
            continue
        current = tuple(
            current[i] + segment.translation_m[i] for i in range(3)
        )  # type: ignore[assignment]
        if not workspace.contains(current):
            raise GuardError(
                "WORKSPACE_VIOLATION",
                f"segment {index} target {current} is outside workspace",
            )
