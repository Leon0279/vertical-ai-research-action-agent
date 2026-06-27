"""Evidence service contracts."""

from app.services.evidence.contracts.evidence_processing_service_protocol import (
    EvidenceProcessingServiceProtocol,
)
from app.services.evidence.contracts.evidence_processor_protocol import EvidenceProcessorProtocol

__all__ = ["EvidenceProcessingServiceProtocol", "EvidenceProcessorProtocol"]
