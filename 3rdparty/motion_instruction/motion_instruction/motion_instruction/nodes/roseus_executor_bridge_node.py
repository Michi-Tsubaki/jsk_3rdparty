from __future__ import annotations

import threading

import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.node import Node

from motion_instruction.bridge import RoseusClient, result_status_code
from motion_instruction.models.errors import ProtocolError
from motion_instruction.nodes.message_conversion import resolved_segment_from_msg
from motion_instruction_interfaces.action import RelativeCartesianMove


_RESULT_STATUS_TO_CONSTANT = {
    "SUCCEEDED": RelativeCartesianMove.Result.SUCCEEDED,
    "REJECTED_COLLISION": RelativeCartesianMove.Result.REJECTED_COLLISION,
    "IK_FAILURE": RelativeCartesianMove.Result.IK_FAILURE,
    "BUSY": RelativeCartesianMove.Result.BUSY,
    "EXECUTOR_UNAVAILABLE": RelativeCartesianMove.Result.EXECUTOR_UNAVAILABLE,
    "EXECUTION_FAILED": RelativeCartesianMove.Result.EXECUTION_FAILED,
}


class RoseusExecutorBridgeNode(Node):
    def __init__(self) -> None:
        super().__init__("roseus_executor_bridge")
        self.declare_parameter("host", "127.0.0.1")
        self.declare_parameter("port", 50950)
        self.declare_parameter("connect_timeout_s", 2.0)
        self.declare_parameter("request_timeout_s", 60.0)
        self.client = RoseusClient(
            host=str(self.get_parameter("host").value),
            port=int(self.get_parameter("port").value),
            connect_timeout_s=float(self.get_parameter("connect_timeout_s").value),
            request_timeout_s=float(self.get_parameter("request_timeout_s").value),
        )
        self._lock = threading.Lock()
        self._seen_command_ids: set[str] = set()
        self._server = ActionServer(
            self,
            RelativeCartesianMove,
            "/motion_instruction/relative_cartesian_move",
            execute_callback=self._execute_callback,
            goal_callback=self._goal_callback,
            cancel_callback=self._cancel_callback,
        )

    def _goal_callback(self, goal_request) -> GoalResponse:
        if self._lock.locked():
            return GoalResponse.REJECT
        if goal_request.command_id in self._seen_command_ids:
            return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    def _cancel_callback(self, goal_handle) -> CancelResponse:
        return CancelResponse.ACCEPT

    def _execute_callback(self, goal_handle):
        goal = goal_handle.request
        result = RelativeCartesianMove.Result()
        if not self._lock.acquire(blocking=False):
            result.status = RelativeCartesianMove.Result.BUSY
            result.code = "BUSY"
            result.message = "executor is busy"
            goal_handle.abort()
            return result

        self._seen_command_ids.add(goal.command_id)
        try:
            segments = [resolved_segment_from_msg(segment) for segment in goal.segments]

            def feedback_callback(message):
                feedback = RelativeCartesianMove.Feedback()
                feedback.current_segment = int(message.get("current_segment", 0))
                feedback.total_segments = int(message.get("total_segments", len(segments)))
                feedback.phase = str(message.get("phase", ""))
                feedback.progress = float(message.get("progress", 0.0))
                feedback.message = str(message.get("message", ""))
                goal_handle.publish_feedback(feedback)

            worker_result = self.client.execute_motion(
                command_id=goal.command_id,
                end_effector=goal.end_effector,
                segments=segments,
                dry_run=goal.dry_run,
                feedback_callback=feedback_callback,
            )
            self._fill_result(result, worker_result)
            if result.status == RelativeCartesianMove.Result.SUCCEEDED:
                goal_handle.succeed()
            else:
                goal_handle.abort()
            return result
        except ProtocolError as exc:
            result.status = RelativeCartesianMove.Result.EXECUTOR_UNAVAILABLE
            result.code = exc.code
            result.message = exc.message
            goal_handle.abort()
            return result
        finally:
            self._lock.release()

    def _fill_result(self, result, worker_result) -> None:
        status_name = result_status_code(worker_result)
        result.status = _RESULT_STATUS_TO_CONSTANT.get(
            status_name,
            RelativeCartesianMove.Result.EXECUTION_FAILED,
        )
        result.code = str(worker_result.get("code", "OK" if worker_result.get("success") else "EXECUTION_FAILED"))
        result.message = str(worker_result.get("message", ""))
        result.completed_segments = int(worker_result.get("completed_segments", 0))
        result.collision = bool(worker_result.get("collision", False))
        result.collision_type = str(worker_result.get("collision_type", "none"))
        result.collision_pairs = list(worker_result.get("collision_pairs", []))


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = RoseusExecutorBridgeNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
