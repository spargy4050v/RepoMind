"""Local, auditable document ingestion for reviewer-confirmed scheme records."""

from .extract import ExtractionResult, extract_upload

__all__ = ["ExtractionResult", "extract_upload"]
