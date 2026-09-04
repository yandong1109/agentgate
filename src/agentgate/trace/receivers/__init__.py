"""Trace receiver entry points."""

from .otlp_http import ingest_otlp_http_json
from .trace_sdk import TraceSdkFileReceiver

__all__ = ["ingest_otlp_http_json", "TraceSdkFileReceiver"]
