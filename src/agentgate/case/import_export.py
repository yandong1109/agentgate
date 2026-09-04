"""Canonical JSON import/export for Dataset versions."""

from __future__ import annotations

from typing import Any, Literal

from agentgate.domain import Dataset, DatasetVersion, DomainModel


class DatasetExport(DomainModel):
    format: Literal["agentgate.dataset"] = "agentgate.dataset"
    format_version: Literal["1"] = "1"
    dataset: Dataset
    version: DatasetVersion


def build_export(dataset: Dataset, version: DatasetVersion) -> DatasetExport:
    if dataset.id != version.dataset_id:
        raise ValueError("Dataset and DatasetVersion identities do not match")
    return DatasetExport(dataset=dataset, version=version)


def parse_export(payload: dict[str, Any] | str) -> DatasetExport:
    if isinstance(payload, str):
        return DatasetExport.model_validate_json(payload)
    return DatasetExport.model_validate(payload)
