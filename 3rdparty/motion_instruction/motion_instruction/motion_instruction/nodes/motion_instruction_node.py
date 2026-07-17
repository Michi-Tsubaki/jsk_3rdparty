from __future__ import annotations

from pathlib import Path
import uuid

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from std_msgs.msg import String

from motion_instruction.confirmation import ApprovalDecision, ConfirmationManager
from motion_instruction.guard import CommandGuard
from motion_instruction.models import GuardConfig, MotionInstructionError, ProviderError
from motion_instruction.nodes.message_conversion import parsed_command_to_msg, resolved_segment_to_msg
from motion_instruction.nodes.speech_phrases import approval_speech, rejection_speech
from motion_instruction.providers import build_provider
from motion_instruction.resolver import RelativeCartesianResolver
from motion_instruction_interfaces.action import RelativeCartesianMove
from motion_instruction_interfaces.msg import ApprovalRequest, MotionStatus, ParsedCommand
from motion_instruction_interfaces.srv import ApproveMotion

try:
    from sound_play_msgs.msg import SoundRequest
except Exception:  # pragma: no cover - optional runtime dependency
    SoundRequest = None


class MotionInstructionNode(Node):
    def __init__(self) -> None:
        super().__init__("motion_instruction_node")
        self.declare_parameter("provider", "azure_openai")
        self.declare_parameter("api_config_path", "")
        self.declare_parameter("prompt_path", "")
        self.declare_parameter("input_topic", "/language_command")
        self.declare_parameter("speech_input_topic", "")
        self.declare_parameter("approval_response_topic", "/motion_instruction/approval_response")
        self.declare_parameter("speech_response_topic", "/motion_instruction/speech_response")
        self.declare_parameter("voicevox_enabled", True)
        self.declare_parameter("voicevox_sound_topic", "/robotsound_jp")
        self.declare_parameter("voicevox_voice", "2")
        self.declare_parameter("voicevox_volume", 1.0)
        self.declare_parameter("execution_mode", "voice_confirm")
        self.declare_parameter("confirmation_timeout_s", 15.0)
        self.declare_parameter("default_frame_id", "base_link")
        self.declare_parameter("execution_frame_id", "base_link")
        self.declare_parameter("default_end_effector", "right_hand")
        self.declare_parameter("default_translation_direction", "forward")
        self.declare_parameter("default_translation_axis", "x")
        self.declare_parameter("default_translation_axis_direction", "positive")
        self.declare_parameter("default_translation_m", 0.010)
        self.declare_parameter("default_rotation_axis", "z")
        self.declare_parameter("default_rotation_direction", "positive")
        self.declare_parameter("default_rotation_rad", 0.17453292519943295)
        self.declare_parameter("allowed_frames", ["base_link", "torso_link", "right_tool", "left_tool"])

        config = GuardConfig(
            default_frame_id=self.get_parameter("default_frame_id").value,
            execution_frame_id=self.get_parameter("execution_frame_id").value,
            default_end_effector=self.get_parameter("default_end_effector").value,
            default_translation_direction=self.get_parameter("default_translation_direction").value,
            default_translation_axis=self.get_parameter("default_translation_axis").value,
            default_translation_axis_direction=self.get_parameter(
                "default_translation_axis_direction"
            ).value,
            default_translation_m=float(self.get_parameter("default_translation_m").value),
            default_rotation_axis=self.get_parameter("default_rotation_axis").value,
            default_rotation_direction=self.get_parameter("default_rotation_direction").value,
            default_rotation_rad=float(self.get_parameter("default_rotation_rad").value),
            allowed_frames=tuple(self.get_parameter("allowed_frames").value),
        )
        self.provider = build_provider(
            str(self.get_parameter("provider").value),
            str(self.get_parameter("api_config_path").value),
            _load_system_prompt(str(self.get_parameter("prompt_path").value)),
        )
        self.guard = CommandGuard(config)
        self.resolver = RelativeCartesianResolver()
        self.confirmation = ConfirmationManager(
            timeout_s=float(self.get_parameter("confirmation_timeout_s").value)
        )
        self._pending_goal: tuple[str, str, list] | None = None

        self.parsed_pub = self.create_publisher(ParsedCommand, "/motion_instruction/parsed_command", 10)
        self.status_pub = self.create_publisher(MotionStatus, "/motion_instruction/status", 20)
        self.speech_pub = self.create_publisher(
            String,
            self.get_parameter("speech_response_topic").value,
            10,
        )
        self.voicevox_pub = None
        self._voicevox_sound_request_type = SoundRequest
        self._voicevox_voice = str(self.get_parameter("voicevox_voice").value)
        self._voicevox_volume = float(self.get_parameter("voicevox_volume").value)
        if _parameter_as_bool(self.get_parameter("voicevox_enabled").value):
            if SoundRequest is None:
                self.get_logger().warning(
                    "voicevox_enabled is true, but sound_play_msgs is not available"
                )
            else:
                self.voicevox_pub = self.create_publisher(
                    SoundRequest,
                    str(self.get_parameter("voicevox_sound_topic").value),
                    10,
                )
        self.approval_pub = self.create_publisher(
            ApprovalRequest,
            "/motion_instruction/approval_request",
            1,
        )
        input_topic = str(self.get_parameter("input_topic").value)
        speech_input_topic = str(self.get_parameter("speech_input_topic").value)
        approval_response_topic = str(self.get_parameter("approval_response_topic").value)

        self.create_subscription(
            String,
            input_topic,
            self._on_language_command,
            10,
        )
        if speech_input_topic and speech_input_topic not in (input_topic, approval_response_topic):
            self.create_subscription(
                String,
                speech_input_topic,
                self._on_speech_input,
                10,
            )
        self.create_subscription(
            String,
            approval_response_topic,
            self._on_approval_response,
            10,
        )
        self.create_service(ApproveMotion, "/motion_instruction/approve", self._on_approve_service)
        self.action_client = ActionClient(
            self,
            RelativeCartesianMove,
            "/motion_instruction/relative_cartesian_move",
        )

    def _on_language_command(self, message: String) -> None:
        command_id = str(uuid.uuid4())
        self._publish_status(command_id, MotionStatus.RECEIVED, "OK", "received", False, 0, 0)
        try:
            parsed = self.provider.parse_motion(message.data)
            self.parsed_pub.publish(
                parsed_command_to_msg(
                    parsed,
                    command_id=command_id,
                    original_text=message.data,
                    provider=self.provider.provider_name,
                    model=self.provider.model_name,
                )
            )
            domain_command = self.guard.validate(
                parsed,
                original_text=message.data,
                provider=self.provider.provider_name,
                model=self.provider.model_name,
                command_id=command_id,
            )
            resolved = self.resolver.resolve(domain_command)
        except MotionInstructionError as exc:
            self._reject(
                command_id,
                exc.code,
                exc.message,
                requires_user_action=(exc.code == "AMBIGUOUS_COMMAND"),
            )
            return

        mode = str(self.get_parameter("execution_mode").value)
        if mode == "voice_confirm":
            summary = self._summary(domain_command.end_effector, domain_command.frame_id, resolved)
            try:
                self.confirmation.start(command_id, summary)
            except MotionInstructionError as exc:
                self._reject(command_id, exc.code, exc.message)
                return
            self._pending_goal = (command_id, domain_command.end_effector, resolved)
            self._publish_approval(command_id, summary)
            self._publish_speech(approval_speech(domain_command.end_effector))
            self._publish_status(
                command_id,
                MotionStatus.WAITING_APPROVAL,
                "OK",
                summary,
                True,
                0,
                len(resolved),
            )
            return
        self._dispatch(command_id, domain_command.end_effector, resolved, dry_run=(mode == "dry_run"))

    def _on_speech_input(self, message: String) -> None:
        if self._pending_goal is not None:
            decision = self.confirmation.decide_voice(message.data)
            if decision != ApprovalDecision.UNKNOWN:
                self._handle_approval_decision(decision, rejected_message=decision.value)
                return
        self._on_language_command(message)

    def _on_approval_response(self, message: String) -> None:
        decision = self.confirmation.decide_voice(message.data)
        self._handle_approval_decision(decision, rejected_message=decision.value)

    def _handle_approval_decision(self, decision: ApprovalDecision, *, rejected_message: str) -> None:
        if self._pending_goal is None:
            return
        command_id, end_effector, resolved = self._pending_goal
        if decision == ApprovalDecision.APPROVED:
            self._pending_goal = None
            self._dispatch(command_id, end_effector, resolved, dry_run=False)
        elif decision in (ApprovalDecision.REJECTED, ApprovalDecision.TIMEOUT):
            self._pending_goal = None
            code = "APPROVAL_REJECTED" if decision == ApprovalDecision.REJECTED else "APPROVAL_TIMEOUT"
            self._reject(command_id, code, rejected_message)

    def _on_approve_service(self, request, response):
        decision = self.confirmation.decide_service(request.command_id, request.approve)
        response.accepted = decision in (ApprovalDecision.APPROVED, ApprovalDecision.REJECTED)
        response.message = decision.value
        self._handle_approval_decision(decision, rejected_message="approval rejected")
        return response

    def _dispatch(self, command_id: str, end_effector: str, resolved: list, dry_run: bool) -> None:
        if not self.action_client.wait_for_server(timeout_sec=0.1):
            self._reject(command_id, "EXECUTOR_UNAVAILABLE", "action server is unavailable")
            return
        goal = RelativeCartesianMove.Goal()
        goal.command_id = command_id
        goal.end_effector = end_effector
        goal.dry_run = dry_run
        goal.segments = [resolved_segment_to_msg(segment) for segment in resolved]
        future = self.action_client.send_goal_async(goal)
        future.add_done_callback(lambda done: self._on_goal_response(command_id, done))
        self._publish_status(
            command_id,
            MotionStatus.PREFLIGHT,
            "OK",
            "sent to executor",
            False,
            0,
            len(resolved),
        )

    def _on_goal_response(self, command_id: str, future) -> None:
        goal_handle = future.result()
        if not goal_handle.accepted:
            self._reject(command_id, "BUSY", "executor rejected the goal")
            return
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(lambda done: self._on_action_result(command_id, done))

    def _on_action_result(self, command_id: str, future) -> None:
        result = future.result().result
        if result.status == RelativeCartesianMove.Result.SUCCEEDED:
            self._publish_status(
                command_id,
                MotionStatus.SUCCEEDED,
                result.code,
                result.message,
                False,
                result.completed_segments,
                result.completed_segments,
            )
            return
        self._reject(command_id, result.code, result.message, collision=result.collision)

    def _reject(
        self,
        command_id: str,
        code: str,
        message: str,
        *,
        requires_user_action: bool = False,
        collision: bool = False,
    ) -> None:
        self._publish_status(
            command_id,
            MotionStatus.REJECTED,
            code,
            message,
            requires_user_action,
            0,
            0,
        )
        self._publish_speech(rejection_speech(code, message, collision=collision))

    def _publish_status(
        self,
        command_id: str,
        state: int,
        code: str,
        message: str,
        requires_user_action: bool,
        current_segment: int,
        total_segments: int,
    ) -> None:
        status = MotionStatus()
        status.command_id = command_id
        status.state = state
        status.code = code
        status.message = message
        status.requires_user_action = requires_user_action
        status.current_segment = current_segment
        status.total_segments = total_segments
        self.status_pub.publish(status)

    def _publish_speech(self, text: str) -> None:
        message = String()
        message.data = text
        self.speech_pub.publish(message)
        voicevox_pub = getattr(self, "voicevox_pub", None)
        sound_request_type = getattr(self, "_voicevox_sound_request_type", None)
        if voicevox_pub is None or sound_request_type is None:
            return
        request = sound_request_type()
        request.sound = sound_request_type.SAY
        request.command = sound_request_type.PLAY_ONCE
        request.volume = float(getattr(self, "_voicevox_volume", 1.0))
        request.arg = text
        request.arg2 = str(getattr(self, "_voicevox_voice", ""))
        voicevox_pub.publish(request)

    def _publish_approval(self, command_id: str, summary: str) -> None:
        request = ApprovalRequest()
        request.command_id = command_id
        request.summary = summary
        self.approval_pub.publish(request)

    def _summary(self, end_effector: str, frame_id: str, resolved: list) -> str:
        return f"{end_effector} in {frame_id}: {len(resolved)} motion segment(s). Execute?"


def _load_system_prompt(prompt_path: str) -> str:
    path = _resolve_data_path(prompt_path, Path("cfg/prompts/motion_parser_ja.txt"))
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ProviderError("PROVIDER_ERROR", f"failed to read system prompt: {path}") from exc


def _resolve_data_path(path_value: str, default_relative_path: Path) -> Path:
    if path_value:
        requested = Path(path_value).expanduser()
        if requested.is_absolute():
            return requested
        candidates = [Path.cwd() / requested, _package_root() / requested]
        candidates.extend(_share_path_candidates(requested))
    else:
        candidates = [_package_root() / default_relative_path]
        candidates.extend(_share_path_candidates(default_relative_path))

    for path in candidates:
        if path.is_file():
            return path
    return candidates[0]


def _share_path_candidates(relative_path: Path) -> list[Path]:
    try:
        from ament_index_python.packages import get_package_share_directory
    except Exception:
        return []
    try:
        return [Path(get_package_share_directory("motion_instruction")) / relative_path]
    except Exception:
        return []


def _package_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _parameter_as_bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = MotionInstructionNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
