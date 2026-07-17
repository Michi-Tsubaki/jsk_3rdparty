from motion_instruction.models.llm_schema import LLMParsedCommand
from motion_instruction.providers.base import MotionLLMProvider


class MotionParser:
    def __init__(self, provider: MotionLLMProvider) -> None:
        self.provider = provider

    def parse(self, instruction: str) -> LLMParsedCommand:
        return self.provider.parse_motion(instruction)
