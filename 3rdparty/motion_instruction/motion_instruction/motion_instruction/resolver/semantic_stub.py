from motion_instruction.models.domain import DomainParsedCommand, ResolvedMotionSegment
from motion_instruction.models.errors import ResolverError


class SemanticMotionResolverStub:
    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled

    def supports(self, command: DomainParsedCommand) -> bool:
        return any(segment.kind.startswith("semantic_") for segment in command.segments)

    def resolve(self, command: DomainParsedCommand) -> list[ResolvedMotionSegment]:
        if self.supports(command):
            raise ResolverError("UNSUPPORTED_INTENT", "semantic motion resolution is not implemented")
        return []
