import math

from motion_instruction.models.errors import GuardError


def _require_finite_positive(value: float, what: str) -> None:
    if not math.isfinite(value):
        raise GuardError("INVALID_SCHEMA", f"{what} must be finite")
    if value <= 0.0:
        raise GuardError("INVALID_SCHEMA", f"{what} must be positive")


def length_to_m(value: float, unit: str) -> float:
    _require_finite_positive(value, "length")
    factors = {"mm": 0.001, "cm": 0.01, "m": 1.0}
    try:
        return value * factors[unit]
    except KeyError as exc:
        raise GuardError("INVALID_SCHEMA", f"invalid length unit: {unit}") from exc


def angle_to_rad(value: float, unit: str) -> float:
    _require_finite_positive(value, "angle")
    factors = {"deg": math.pi / 180.0, "rad": 1.0}
    try:
        return value * factors[unit]
    except KeyError as exc:
        raise GuardError("INVALID_SCHEMA", f"invalid angle unit: {unit}") from exc


def duration_to_ms(value: float, unit: str) -> int:
    _require_finite_positive(value, "duration")
    factors = {"ms": 1.0, "s": 1000.0}
    try:
        duration_ms = value * factors[unit]
    except KeyError as exc:
        raise GuardError("INVALID_SCHEMA", f"invalid duration unit: {unit}") from exc
    if not math.isfinite(duration_ms) or duration_ms <= 0.0:
        raise GuardError("INVALID_SCHEMA", "duration must be positive")
    return int(round(duration_ms))
