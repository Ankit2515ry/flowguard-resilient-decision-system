"""Versioned structural input schemas, separate from business eligibility rules."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml


class InputSchemaError(ValueError):
    """Input data does not match the selected workflow version's structural schema."""


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(loader: _UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise InputSchemaError(f"duplicate YAML key {key!r} in input schema")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping)


_ALLOWED_TYPES = {"object", "string", "integer", "number", "boolean", "array"}


def load_input_schema(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    try:
        with file_path.open("r", encoding="utf-8") as stream:
            schema = yaml.load(stream, Loader=_UniqueKeyLoader)
    except (OSError, yaml.YAMLError) as exc:
        raise InputSchemaError(f"could not load input schema {file_path}: {exc}") from exc
    _validate_schema(schema, "$schema")
    return schema


def _validate_schema(schema: Any, location: str) -> None:
    if not isinstance(schema, dict) or schema.get("type") not in _ALLOWED_TYPES:
        raise InputSchemaError(f"{location} must declare a supported type")
    if schema["type"] == "object":
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if not isinstance(properties, dict) or not isinstance(required, list):
            raise InputSchemaError(f"{location} object properties/required have invalid shape")
        if any(not isinstance(key, str) for key in properties) or any(
            not isinstance(key, str) for key in required
        ):
            raise InputSchemaError(f"{location} property names must be strings")
        unknown = set(required) - set(properties)
        if unknown:
            raise InputSchemaError(f"{location} required fields lack schemas: {sorted(unknown)}")
        for key, child in properties.items():
            _validate_schema(child, f"{location}.{key}")
    elif schema["type"] == "array":
        if "items" not in schema:
            raise InputSchemaError(f"{location} array schema requires items")
        _validate_schema(schema["items"], f"{location}[]")


def validate_input(data: Any, schema: dict[str, Any]) -> None:
    """Validate types and required structure without evaluating business rules."""
    _validate_value(data, schema, "data")


def _validate_value(value: Any, schema: dict[str, Any], location: str) -> None:
    kind = schema["type"]
    matches = {
        "object": isinstance(value, Mapping),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "array": isinstance(value, list),
    }[kind]
    if not matches:
        raise InputSchemaError(f"{location} must be of type {kind}")
    if kind == "object":
        for field in schema.get("required", []):
            if field not in value:
                raise InputSchemaError(f"{location}.{field} is required")
        for field, child_schema in schema.get("properties", {}).items():
            if field in value:
                _validate_value(value[field], child_schema, f"{location}.{field}")
    elif kind == "array":
        for index, item in enumerate(value):
            _validate_value(item, schema["items"], f"{location}[{index}]")
