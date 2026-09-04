"""Shared immutable domain-model utilities."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict
from pydantic_core import core_schema


class FrozenJsonObject(Mapping[str, Any]):
    """Recursively immutable JSON object with Pydantic serialization support."""

    __slots__ = ("_data",)

    def __init__(self, value: Mapping[str, Any] | None = None) -> None:
        self._data = {str(key): freeze_json(item) for key, item in (value or {}).items()}

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return f"FrozenJsonObject({self._data!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Mapping) and dict(self.items()) == dict(other.items())

    def to_dict(self) -> dict[str, Any]:
        return {key: thaw_json(value) for key, value in self._data.items()}

    @classmethod
    def __get_pydantic_core_schema__(cls, _source: Any, _handler: Any) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            lambda value: value if isinstance(value, cls) else cls(value),
            core_schema.dict_schema(core_schema.str_schema(), core_schema.any_schema()),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda value: value.to_dict(), when_used="always"
            ),
        )


FrozenJsonValue = Any


def freeze_json(value: Any) -> Any:
    if isinstance(value, FrozenJsonObject):
        return value
    if isinstance(value, Mapping):
        return FrozenJsonObject(value)
    if isinstance(value, (list, tuple)):
        return tuple(freeze_json(item) for item in value)
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise TypeError(f"value is not JSON-compatible: {type(value).__name__}")


def thaw_json(value: Any) -> Any:
    if isinstance(value, FrozenJsonObject):
        return value.to_dict()
    if isinstance(value, Mapping):
        return {str(key): thaw_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [thaw_json(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(
        thaw_json(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    )


def content_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class DomainModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)
