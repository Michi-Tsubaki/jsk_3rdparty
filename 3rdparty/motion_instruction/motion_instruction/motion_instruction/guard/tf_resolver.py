from collections.abc import Callable

from motion_instruction.models.errors import GuardError


VectorTransform = Callable[[str, str, tuple[float, float, float]], tuple[float, float, float]]


class StaticFrameResolver:
    def __init__(
        self,
        execution_frame_id: str,
        transform_vector: VectorTransform | None = None,
    ) -> None:
        self.execution_frame_id = execution_frame_id
        self._transform_vector = transform_vector

    def resolve_vector(
        self,
        source_frame_id: str,
        vector: tuple[float, float, float],
    ) -> tuple[str, tuple[float, float, float]]:
        if source_frame_id == self.execution_frame_id:
            return self.execution_frame_id, vector
        if self._transform_vector is None:
            raise GuardError(
                "TF_UNAVAILABLE",
                f"no transform from {source_frame_id} to {self.execution_frame_id}",
            )
        return (
            self.execution_frame_id,
            self._transform_vector(source_frame_id, self.execution_frame_id, vector),
        )
