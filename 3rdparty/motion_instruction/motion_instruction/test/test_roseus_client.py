import socket
import threading

from motion_instruction.bridge.protocol import PROTOCOL_VERSION, decode_line, encode_message
from motion_instruction.bridge.roseus_client import RoseusClient
from motion_instruction.models.domain import ResolvedMotionSegment


class FakeWorker:
    def __init__(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(("127.0.0.1", 0))
        self.server.listen(1)
        self.port = self.server.getsockname()[1]
        self.request = None
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def close(self):
        self.server.close()
        self.thread.join(timeout=1.0)

    def _serve(self):
        conn, _ = self.server.accept()
        with conn:
            request_line = conn.makefile("rb").readline()
            self.request = decode_line(request_line)
            feedback = {
                "protocol_version": PROTOCOL_VERSION,
                "type": "feedback",
                "request_id": self.request["request_id"],
                "phase": "preflight",
                "current_segment": 0,
                "total_segments": 1,
                "progress": 0.5,
                "message": "checking",
            }
            result = {
                "protocol_version": PROTOCOL_VERSION,
                "type": "result",
                "request_id": self.request["request_id"],
                "success": True,
                "code": "OK",
                "message": "done",
                "completed_segments": 1,
                "collision": False,
                "collision_type": "none",
                "collision_pairs": [],
            }
            conn.sendall(encode_message(feedback))
            conn.sendall(encode_message(result))


def test_client_forwards_request_feedback_and_result():
    worker = FakeWorker()
    feedback = []
    try:
        client = RoseusClient(port=worker.port, request_timeout_s=2.0)
        result = client.execute_motion(
            command_id="cmd",
            end_effector="right_hand",
            dry_run=False,
            feedback_callback=feedback.append,
            segments=[
                ResolvedMotionSegment(
                    kind="translation",
                    frame_id="base_link",
                    translation_m=(0.0, 0.05, 0.0),
                    duration_ms=5000,
                )
            ],
        )
        assert worker.request["type"] == "execute_motion"
        assert worker.request["segments"][0]["translation_mm"] == [0.0, 50.0, 0.0]
        assert feedback[0]["phase"] == "preflight"
        assert result["success"] is True
        assert result["completed_segments"] == 1
    finally:
        worker.close()
