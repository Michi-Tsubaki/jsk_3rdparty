from motion_instruction.models.errors import ResolverError


_AXES = {
    "x": (1.0, 0.0, 0.0),
    "y": (0.0, 1.0, 0.0),
    "z": (0.0, 0.0, 1.0),
}

_TRANSLATION_DIRECTIONS = {
    "forward": (1.0, 0.0, 0.0),
    "backward": (-1.0, 0.0, 0.0),
    "left": (0.0, 1.0, 0.0),
    "right": (0.0, -1.0, 0.0),
    "up": (0.0, 0.0, 1.0),
    "down": (0.0, 0.0, -1.0),
}

_ROTATION_DIRECTION_SIGNS = {
    "positive": 1.0,
    "negative": -1.0,
    "counterclockwise": 1.0,
    "clockwise": -1.0,
}


def _scale(vector: tuple[float, float, float], magnitude: float) -> tuple[float, float, float]:
    return tuple(component * magnitude for component in vector)  # type: ignore[return-value]


def translation_vector(direction: str, axis: str, magnitude_m: float) -> tuple[float, float, float]:
    if direction in _TRANSLATION_DIRECTIONS and axis == "unspecified":
        return _scale(_TRANSLATION_DIRECTIONS[direction], magnitude_m)
    if axis in _AXES and direction in ("positive", "negative"):
        sign = 1.0 if direction == "positive" else -1.0
        return _scale(_AXES[axis], sign * magnitude_m)
    raise ResolverError(
        "UNSUPPORTED_INTENT",
        f"cannot resolve translation direction={direction} axis={axis}",
    )


def rotation_axis(direction: str, axis: str) -> tuple[float, float, float]:
    if axis not in _AXES:
        raise ResolverError("AMBIGUOUS_COMMAND", "rotation axis must be x, y, or z")
    if direction not in _ROTATION_DIRECTION_SIGNS:
        raise ResolverError("AMBIGUOUS_COMMAND", "rotation direction must be positive or negative")
    return _scale(_AXES[axis], _ROTATION_DIRECTION_SIGNS[direction])
