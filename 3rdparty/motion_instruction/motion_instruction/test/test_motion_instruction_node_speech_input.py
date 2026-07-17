from __future__ import annotations

from std_msgs.msg import String

from motion_instruction.confirmation import ConfirmationManager
from motion_instruction.nodes.motion_instruction_node import MotionInstructionNode


def _make_message(text: str) -> String:
    message = String()
    message.data = text
    return message


def test_speech_input_approves_pending_goal() -> None:
    node = MotionInstructionNode.__new__(MotionInstructionNode)
    node.confirmation = ConfirmationManager()
    node.confirmation.start("command-1", "summary")
    node._pending_goal = ("command-1", "right_hand", ["segment"])
    dispatched = []
    node._dispatch = lambda *args, **kwargs: dispatched.append((args, kwargs))
    node._reject = lambda *args, **kwargs: None

    MotionInstructionNode._on_speech_input(node, _make_message("はい"))

    assert node._pending_goal is None
    assert dispatched == [(("command-1", "right_hand", ["segment"]), {"dry_run": False})]


def test_speech_input_falls_back_to_language_command_when_not_approval() -> None:
    node = MotionInstructionNode.__new__(MotionInstructionNode)
    node.confirmation = ConfirmationManager()
    node.confirmation.start("command-1", "summary")
    node._pending_goal = ("command-1", "right_hand", ["segment"])
    commands = []
    node._on_language_command = lambda message: commands.append(message.data)

    MotionInstructionNode._on_speech_input(node, _make_message("左に5cm"))

    assert node._pending_goal == ("command-1", "right_hand", ["segment"])
    assert commands == ["左に5cm"]
