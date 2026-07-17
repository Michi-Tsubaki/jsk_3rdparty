class MotionInstructionError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


class ProviderError(MotionInstructionError):
    pass


class GuardError(MotionInstructionError):
    pass


class ResolverError(MotionInstructionError):
    pass


class ProtocolError(MotionInstructionError):
    pass
