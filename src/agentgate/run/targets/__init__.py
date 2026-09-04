"""Target execution adapter API."""

from .base import (
    CredentialResolver,
    EnvCredentialResolver,
    ResolvedCredential,
    TargetExecutionAdapter,
    TargetIntegrationError,
)
from .http import HttpTargetAdapter
from .python_fn import PythonFunctionTarget

__all__ = [
    "CredentialResolver",
    "EnvCredentialResolver",
    "HttpTargetAdapter",
    "PythonFunctionTarget",
    "ResolvedCredential",
    "TargetExecutionAdapter",
    "TargetIntegrationError",
]
