from __future__ import annotations

from sound_play_msgs.msg import SoundRequest

from motion_instruction.nodes.motion_instruction_node import MotionInstructionNode
from motion_instruction.nodes.speech_phrases import approval_speech, rejection_speech


class _Publisher:
    def __init__(self) -> None:
        self.messages = []

    def publish(self, message) -> None:
        self.messages.append(message)


def test_ambiguous_axis_uses_fixed_voicevox_phrase() -> None:
    assert rejection_speech("AMBIGUOUS_COMMAND", "Which axis should I rotate around?") == "回転軸は何ですか？"


def test_ambiguous_hand_uses_fixed_voicevox_phrase() -> None:
    assert rejection_speech("AMBIGUOUS_COMMAND", "左手ですか？") == "右手ですか、左手ですか？"


def test_provider_error_does_not_speak_provider_exception() -> None:
    assert rejection_speech("PROVIDER_ERROR", "NotFoundError: deployment does not exist") == "失敗しました。"


def test_approval_speech_names_known_end_effector() -> None:
    assert approval_speech("right_hand") == "右手を動かします。実行しますか？"


def test_publish_speech_sends_string_and_voicevox_request() -> None:
    node = MotionInstructionNode.__new__(MotionInstructionNode)
    node.speech_pub = _Publisher()
    node.voicevox_pub = _Publisher()
    node._voicevox_sound_request_type = SoundRequest
    node._voicevox_voice = "2"
    node._voicevox_volume = 0.8

    MotionInstructionNode._publish_speech(node, "失敗しました。")

    assert node.speech_pub.messages[0].data == "失敗しました。"
    request = node.voicevox_pub.messages[0]
    assert request.sound == SoundRequest.SAY
    assert request.command == SoundRequest.PLAY_ONCE
    assert request.arg == "失敗しました。"
    assert request.arg2 == "2"
    assert request.volume == 0.8
