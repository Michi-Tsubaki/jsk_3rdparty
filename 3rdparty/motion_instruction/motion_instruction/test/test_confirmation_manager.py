from motion_instruction.confirmation import ApprovalDecision, ConfirmationManager
from motion_instruction.models.errors import MotionInstructionError


class Clock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value


def test_positive_phrase_approves_after_normalization():
    clock = Clock()
    manager = ConfirmationManager(monotonic=clock)
    manager.start("cmd", "summary")
    assert manager.decide_voice(" はい。 ") == ApprovalDecision.APPROVED


def test_negative_phrase_rejects():
    clock = Clock()
    manager = ConfirmationManager(monotonic=clock)
    manager.start("cmd", "summary")
    assert manager.decide_voice("キャンセル") == ApprovalDecision.REJECTED


def test_unknown_phrase_does_not_approve():
    clock = Clock()
    manager = ConfirmationManager(monotonic=clock)
    manager.start("cmd", "summary")
    assert manager.decide_voice("maybe") == ApprovalDecision.UNKNOWN
    assert manager.pending is not None


def test_timeout_discards_pending_command():
    clock = Clock()
    manager = ConfirmationManager(timeout_s=1.0, monotonic=clock)
    manager.start("cmd", "summary")
    clock.value = 2.0
    assert manager.decide_voice("はい") == ApprovalDecision.TIMEOUT
    assert manager.pending is None


def test_busy_when_pending():
    clock = Clock()
    manager = ConfirmationManager(monotonic=clock)
    manager.start("cmd", "summary")
    try:
        manager.start("cmd2", "summary")
    except MotionInstructionError as exc:
        assert exc.code == "BUSY"
    else:
        raise AssertionError("expected busy error")
