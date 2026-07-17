from typing import Protocol

from motion_instruction.models.domain import DomainParsedCommand, ResolvedMotionSegment


class MotionResolver(Protocol):
    def supports(self, command: DomainParsedCommand) -> bool:
        ...

    def resolve(self, command: DomainParsedCommand) -> list[ResolvedMotionSegment]:
        ...
