import json

import pytest

from motion_instruction.bridge.protocol import (
    PROTOCOL_VERSION,
    decode_line,
    encode_message,
    make_execute_motion_request,
    result_status_code,
)
from motion_instruction.models.domain import ResolvedMotionSegment
from motion_instruction.models.errors import ProtocolError


def test_request_converts_translation_m_to_mm():
    request = make_execute_motion_request(
        command_id="cmd",
        end_effector="right_hand",
        dry_run=False,
        request_id="req",
        segments=[
            ResolvedMotionSegment(
                kind="translation",
                frame_id="base_link",
                translation_m=(0.0, 0.05, 0.0),
                duration_ms=5000,
            )
        ],
    )
    assert request["segments"][0]["translation_mm"] == [0.0, 50.0, 0.0]


def test_encode_decode_round_trip():
    message = {"protocol_version": PROTOCOL_VERSION, "type": "pong", "request_id": "req"}
    assert decode_line(encode_message(message)) == message


def test_malformed_json_rejected():
    with pytest.raises(ProtocolError):
        decode_line(b"{not-json}\n")


def test_protocol_version_mismatch_rejected():
    with pytest.raises(ProtocolError):
        decode_line(json.dumps({"protocol_version": "9", "type": "pong", "request_id": "req"}))


def test_result_status_mapping_collision():
    result = {
        "protocol_version": PROTOCOL_VERSION,
        "type": "result",
        "request_id": "req",
        "success": False,
        "code": "COLLISION_SELF",
    }
    assert result_status_code(result) == "REJECTED_COLLISION"
