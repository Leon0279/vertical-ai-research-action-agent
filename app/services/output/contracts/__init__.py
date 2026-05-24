"""Output service contracts."""

from app.services.output.contracts.conclusion_generator_protocol import ConclusionGeneratorProtocol
from app.services.output.contracts.response_assembler_protocol import ResponseAssemblerProtocol

__all__ = ["ConclusionGeneratorProtocol", "ResponseAssemblerProtocol"]

