from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass
from enum import Enum

from motion_instruction.models.errors import MotionInstructionError


class ApprovalDecision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    UNKNOWN = "unknown"
    TIMEOUT = "timeout"


@dataclass(frozen=True)
class PendingApproval:
    command_id: str
    summary: str
    expires_at_monotonic: float


class ConfirmationManager:
    def __init__(
        self,
        *,
        positive_phrases: list[str] | None = None,
        negative_phrases: list[str] | None = None,
        timeout_s: float = 15.0,
        monotonic=time.monotonic,
    ) -> None:
        self.positive_phrases = {
            self.normalize(text)
            for text in (positive_phrases or ["はい", "実行", "お願いします", "よいです"])
        }
        self.negative_phrases = {
            self.normalize(text)
            for text in (negative_phrases or ["いいえ", "中止", "やめて", "キャンセル"])
        }
        self.timeout_s = timeout_s
        self._monotonic = monotonic
        self._pending: PendingApproval | None = None

    @property
    def pending(self) -> PendingApproval | None:
        return self._pending

    def start(self, command_id: str, summary: str) -> PendingApproval:
        if self._pending is not None and not self.is_expired():
            raise MotionInstructionError("BUSY", "another command is waiting for approval")
        self._pending = PendingApproval(
            command_id=command_id,
            summary=summary,
            expires_at_monotonic=self._monotonic() + self.timeout_s,
        )
        return self._pending

    def decide_voice(self, text: str) -> ApprovalDecision:
        if self._pending is None:
            return ApprovalDecision.UNKNOWN
        if self.is_expired():
            self._pending = None
            return ApprovalDecision.TIMEOUT
        normalized = self.normalize(text)
        if normalized in self.positive_phrases:
            self._pending = None
            return ApprovalDecision.APPROVED
        if normalized in self.negative_phrases:
            self._pending = None
            return ApprovalDecision.REJECTED
        return ApprovalDecision.UNKNOWN

    def decide_service(self, command_id: str, approve: bool) -> ApprovalDecision:
        if self._pending is None:
            return ApprovalDecision.UNKNOWN
        if self.is_expired():
            self._pending = None
            return ApprovalDecision.TIMEOUT
        if command_id != self._pending.command_id:
            return ApprovalDecision.UNKNOWN
        self._pending = None
        return ApprovalDecision.APPROVED if approve else ApprovalDecision.REJECTED

    def is_expired(self) -> bool:
        return self._pending is not None and self._monotonic() > self._pending.expires_at_monotonic

    @staticmethod
    def normalize(text: str) -> str:
        normalized = unicodedata.normalize("NFKC", text).strip().lower()
        return re.sub(r"[\s、。,.!！?？]+", "", normalized)
