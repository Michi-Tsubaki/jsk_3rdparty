from __future__ import annotations

import json
import uuid
from typing import Any

from motion_instruction.models.domain import ResolvedMotionSegment
from motion_instruction.models.errors import ProtocolError


PROTOCOL_VERSION = "1.0"


def segment_to_wire(segment: ResolvedMotionSegment) -> dict[str, Any]:
    return {
        "kind": segment.kind,
        "frame_id": segment.frame_id,
        "translation_mm": [value * 1000.0 for value in segment.translation_m],
        "rotation_axis": list(segment.rotation_axis),
        "rotation_angle_rad": segment.rotation_angle_rad,
        "duration_ms": segment.duration_ms,
    }


def make_execute_motion_request(
    *,
    command_id: str,
    end_effector: str,
    segments: list[ResolvedMotionSegment],
    dry_run: bool,
    request_id: str | None = None,
) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "type": "execute_motion",
        "request_id": request_id or str(uuid.uuid4()),
        "command_id": command_id,
        "end_effector": end_effector,
        "dry_run": dry_run,
        "segments": [segment_to_wire(segment) for segment in segments],
    }


def make_ping(request_id: str | None = None) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "type": "ping",
        "request_id": request_id or str(uuid.uuid4()),
    }


def encode_message(message: dict[str, Any]) -> bytes:
    return (json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def decode_line(line: bytes | str) -> dict[str, Any]:
    if isinstance(line, bytes):
        line = line.decode("utf-8")
    try:
        message = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ProtocolError("EXECUTOR_UNAVAILABLE", "worker returned malformed JSON") from exc
    if not isinstance(message, dict):
        raise ProtocolError("EXECUTOR_UNAVAILABLE", "worker message must be a JSON object")
    if message.get("protocol_version") != PROTOCOL_VERSION:
        raise ProtocolError(
            "EXECUTOR_UNAVAILABLE",
            f"protocol version mismatch: {message.get('protocol_version')}",
        )
    if not isinstance(message.get("type"), str):
        raise ProtocolError("EXECUTOR_UNAVAILABLE", "worker message missing type")
    if not isinstance(message.get("request_id"), str):
        raise ProtocolError("EXECUTOR_UNAVAILABLE", "worker message missing request_id")
    return message


def result_status_code(result: dict[str, Any]) -> str:
    if result.get("success") is True:
        return "SUCCEEDED"
    code = str(result.get("code", "EXECUTION_FAILED"))
    if code.startswith("COLLISION_"):
        return "REJECTED_COLLISION"
    if code == "IK_FAILURE":
        return "IK_FAILURE"
    if code == "BUSY":
        return "BUSY"
    if code == "EXECUTOR_UNAVAILABLE":
        return "EXECUTOR_UNAVAILABLE"
    return "EXECUTION_FAILED"
