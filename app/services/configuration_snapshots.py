"""Build immutable database snapshots from the Phase 2 YAML loader and input schemas."""

from __future__ import annotations

import hashlib
import json
import hashlib
from pathlib import Path
from typing import Any

from app.engine.config import WorkflowDefinition, load_workflows
from app.services.input_validation import load_input_schema


def configuration_checksum(configuration: dict[str, Any]) -> str:
    canonical = json.dumps(
        configuration, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_config_snapshots(
    workflow_dir: str | Path | None = None,
    schema_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    if workflow_dir is None:
        workflow_dir = Path(__file__).parents[2] / "configs" / "workflows"
    workflow_dir = Path(workflow_dir)
    if schema_dir is None:
        schema_dir = workflow_dir.parent / "input_schemas"
    schema_dir = Path(schema_dir)

    snapshots: list[dict[str, Any]] = []
    for (workflow_id, version), definition in load_workflows(workflow_dir).items():
        schema_path = schema_dir / f"{workflow_id}_v{version}.yaml"
        input_schema = load_input_schema(schema_path)
        configuration = {
            "workflow": definition.model_dump(mode="json"),
            "input_schema": input_schema,
        }
        snapshots.append({
            "workflow_id": workflow_id,
            "version": version,
            "configuration": configuration,
            "checksum": configuration_checksum(configuration),
        })
    return snapshots
