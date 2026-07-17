from __future__ import annotations

import socket
from collections.abc import Callable
from typing import Any

from motion_instruction.bridge.protocol import (
    decode_line,
    encode_message,
    make_execute_motion_request,
    make_ping,
)
from motion_instruction.models.domain import ResolvedMotionSegment
from motion_instruction.models.errors import ProtocolError


FeedbackCallback = Callable[[dict[str, Any]], None]


class RoseusClient:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 50950,
        connect_timeout_s: float = 2.0,
        request_timeout_s: float = 60.0,
    ) -> None:
        self.host = host
        self.port = port
        self.connect_timeout_s = connect_timeout_s
        self.request_timeout_s = request_timeout_s

    def ping(self) -> dict[str, Any]:
        request = make_ping()
        return self._round_trip_until_result(request, result_types={"pong"})

    def execute_motion(
        self,
        *,
        command_id: str,
        end_effector: str,
        segments: list[ResolvedMotionSegment],
        dry_run: bool,
        feedback_callback: FeedbackCallback | None = None,
    ) -> dict[str, Any]:
        request = make_execute_motion_request(
            command_id=command_id,
            end_effector=end_effector,
            segments=segments,
            dry_run=dry_run,
        )
        return self._round_trip_until_result(
            request,
            result_types={"result"},
            feedback_callback=feedback_callback,
        )

    def _round_trip_until_result(
        self,
        request: dict[str, Any],
        *,
        result_types: set[str],
        feedback_callback: FeedbackCallback | None = None,
    ) -> dict[str, Any]:
        try:
            with socket.create_connection(
                (self.host, self.port),
                timeout=self.connect_timeout_s,
            ) as sock:
                sock.settimeout(self.request_timeout_s)
                sock.sendall(encode_message(request))
                with sock.makefile("rb") as reader:
                    for raw_line in reader:
                        message = decode_line(raw_line)
                        if message.get("request_id") != request["request_id"]:
                            continue
                        if message["type"] == "feedback":
                            if feedback_callback is not None:
                                feedback_callback(message)
                            continue
                        if message["type"] in result_types:
                            return message
        except OSError as exc:
            raise ProtocolError("EXECUTOR_UNAVAILABLE", str(exc)) from exc
        raise ProtocolError("EXECUTOR_UNAVAILABLE", "worker closed connection without a result")
