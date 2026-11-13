"""Load, validate, and retain immutable workflow configuration versions."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class ConfigurationError(ValueError):
    """A workflow file is malformed or violates the configuration contract."""


class StageType(str, Enum):
    RULE_EVALUATION = "RULE_EVALUATION"
    EXTERNAL_CALL = "EXTERNAL_CALL"
    HUMAN_TASK = "HUMAN_TASK"
    TERMINAL = "TERMINAL"


class TerminalOutcome(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class FailureAction(str, Enum):
    REJECT = "REJECT"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class Operator(str, Enum):
    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    NOT_IN = "not_in"
    EXISTS = "exists"


class Condition(BaseModel):
    """A leaf test or a non-empty nested all/any group."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    field: str | None = None
    operator: Operator | None = None
    value: Any = None
    all: tuple[Condition, ...] | None = None
    any: tuple[Condition, ...] | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> Condition:
        is_leaf = self.field is not None
        groups = [name for name in ("all", "any") if getattr(self, name) is not None]
        if is_leaf:
            if groups or self.operator is None:
                raise ValueError("a condition leaf requires field and operator, without all/any")
            if not self.field or any(not part for part in self.field.split(".")):
                raise ValueError("field must be a non-empty dot-separated path")
            if "value" not in self.model_fields_set:
                raise ValueError("condition leaf requires value (use exists with true/false)")
            if self.operator is Operator.EXISTS and not isinstance(self.value, bool):
                raise ValueError("exists requires a boolean value")
            if self.operator in (Operator.IN, Operator.NOT_IN):
                if not isinstance(self.value, (list, tuple)):
                    raise ValueError(f"{self.operator.value} requires a list of expected values")
                # Freeze nested operator operands too; the validated version must not be
                # mutable through a list reference retained inside a frozen model.
                object.__setattr__(self, "value", tuple(self.value))
            elif isinstance(self.value, (dict, list, tuple, set)):
                raise ValueError(f"{self.operator.value} requires a scalar expected value")
            return self

        if len(groups) != 1 or self.operator is not None or "value" in self.model_fields_set:
            raise ValueError("a condition must be either a field test or exactly one all/any group")
        children = getattr(self, groups[0])
        if not children:
            raise ValueError(f"{groups[0]} condition group must not be empty")
        return self


Condition.model_rebuild()


class Rule(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    condition: Condition
    on_failure: FailureAction


class RuleSet(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    rules: tuple[Rule, ...] = Field(min_length=1)


class Stage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    type: StageType
    rule_set: str | None = None
    operation: str | None = None
    outcome: TerminalOutcome | None = None


class Transition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    from_stage: str = Field(min_length=1)
    outcome: str = Field(min_length=1)
    to_stage: str = Field(min_length=1)


class WorkflowDefinition(BaseModel):
    """Fully checked workflow version; nested collections are immutable tuples."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    workflow_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    entry_stage: str = Field(min_length=1)
    stages: tuple[Stage, ...] = Field(min_length=1)
    rule_sets: tuple[RuleSet, ...] = ()
    transitions: tuple[Transition, ...] = ()

    @model_validator(mode="after")
    def validate_graph(self) -> WorkflowDefinition:
        stage_by_id = _unique_index(self.stages, "stage")
        rule_sets = _unique_index(self.rule_sets, "rule set")
        if self.entry_stage not in stage_by_id:
            raise ValueError(f"entry_stage {self.entry_stage!r} does not reference a stage")

        seen_rules: set[str] = set()
        for rule_set in self.rule_sets:
            for rule in rule_set.rules:
                if rule.id in seen_rules:
                    raise ValueError(f"duplicate rule id {rule.id!r}")
                seen_rules.add(rule.id)

        for stage in self.stages:
            if stage.type is StageType.RULE_EVALUATION:
                if stage.rule_set not in rule_sets:
                    raise ValueError(
                        f"RULE_EVALUATION stage {stage.id!r} references missing rule_set "
                        f"{stage.rule_set!r}"
                    )
                if stage.operation is not None or stage.outcome is not None:
                    raise ValueError(f"RULE_EVALUATION stage {stage.id!r} has irrelevant fields")
            elif stage.type is StageType.EXTERNAL_CALL:
                if not stage.operation:
                    raise ValueError(f"EXTERNAL_CALL stage {stage.id!r} requires operation")
                if stage.rule_set is not None or stage.outcome is not None:
                    raise ValueError(f"EXTERNAL_CALL stage {stage.id!r} has irrelevant fields")
            elif stage.type is StageType.HUMAN_TASK:
                if stage.rule_set is not None or stage.operation is not None or stage.outcome is not None:
                    raise ValueError(f"HUMAN_TASK stage {stage.id!r} has irrelevant fields")
            elif stage.type is StageType.TERMINAL:
                if stage.outcome is None:
                    raise ValueError(f"TERMINAL stage {stage.id!r} requires an outcome")
                if stage.rule_set is not None or stage.operation is not None:
                    raise ValueError(f"TERMINAL stage {stage.id!r} has irrelevant fields")

        edges: dict[str, list[str]] = {stage_id: [] for stage_id in stage_by_id}
        seen_edges: set[tuple[str, str]] = set()
        allowed_events = {
            StageType.RULE_EVALUATION: {"SUCCESS", "REJECT", "MANUAL_REVIEW"},
            StageType.EXTERNAL_CALL: {"SUCCESS", "FAILURE", "MANUAL_REVIEW"},
            StageType.HUMAN_TASK: {"APPROVED", "REJECTED", "MANUAL_REVIEW"},
            StageType.TERMINAL: set(),
        }
        for transition in self.transitions:
            source = stage_by_id.get(transition.from_stage)
            if source is None:
                raise ValueError(f"transition references missing source stage {transition.from_stage!r}")
            if transition.to_stage not in stage_by_id:
                raise ValueError(f"transition references missing target stage {transition.to_stage!r}")
            if source.type is StageType.TERMINAL:
                raise ValueError(f"terminal stage {source.id!r} cannot have transitions")
            event = transition.outcome.upper()
            if event not in allowed_events[source.type]:
                raise ValueError(
                    f"outcome {transition.outcome!r} is invalid for {source.type.value} stage "
                    f"{source.id!r}; expected one of {sorted(allowed_events[source.type])}"
                )
            key = (source.id, event)
            if key in seen_edges:
                raise ValueError(f"duplicate transition outcome {event!r} from stage {source.id!r}")
            seen_edges.add(key)
            edges[source.id].append(transition.to_stage)

        for stage in self.stages:
            if stage.type is not StageType.TERMINAL and not edges[stage.id]:
                raise ValueError(f"non-terminal stage {stage.id!r} requires at least one transition")

        cycle = _find_cycle(edges)
        if cycle:
            raise ValueError(f"workflow cycles are unsupported; cycle includes {cycle!r}")
        reachable = _reachable(self.entry_stage, edges)
        unreachable = sorted(set(stage_by_id) - reachable)
        if unreachable:
            raise ValueError(f"unreachable stages: {', '.join(unreachable)}")

        terminal_outcomes = {stage.outcome for stage in self.stages if stage.type is StageType.TERMINAL}
        required_outcomes = set(TerminalOutcome)
        terminal_count = sum(stage.type is StageType.TERMINAL for stage in self.stages)
        if terminal_count != len(terminal_outcomes):
            raise ValueError("each terminal outcome must be represented by exactly one stage")
        missing = required_outcomes - terminal_outcomes
        if missing:
            raise ValueError("workflow is missing terminal outcomes: " + ", ".join(x.value for x in missing))
        return self

    def transition_target(self, stage_id: str, outcome: str) -> str:
        """Resolve a validated transition by stage and case-insensitive outcome."""
        normalized = outcome.upper()
        for transition in self.transitions:
            if transition.from_stage == stage_id and transition.outcome.upper() == normalized:
                return transition.to_stage
        raise KeyError(f"no transition for {stage_id!r} / {normalized!r}")


def _unique_index(items: tuple[Any, ...], label: str) -> dict[str, Any]:
    index: dict[str, Any] = {}
    for item in items:
        if item.id in index:
            raise ValueError(f"duplicate {label} id {item.id!r}")
        index[item.id] = item
    return index


def _reachable(start: str, edges: Mapping[str, list[str]]) -> set[str]:
    visited: set[str] = set()
    pending = [start]
    while pending:
        current = pending.pop()
        if current not in visited:
            visited.add(current)
            pending.extend(edges[current])
    return visited


def _find_cycle(edges: Mapping[str, list[str]]) -> list[str] | None:
    active: set[str] = set()
    complete: set[str] = set()
    path: list[str] = []

    def visit(node: str) -> list[str] | None:
        if node in active:
            return path[path.index(node):] + [node]
        if node in complete:
            return None
        active.add(node)
        path.append(node)
        for target in edges[node]:
            found = visit(target)
            if found:
                return found
        path.pop()
        active.remove(node)
        complete.add(node)
        return None

    for node in edges:
        found = visit(node)
        if found:
            return found
    return None


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(loader: _UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False):
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ConfigurationError(f"duplicate YAML key {key!r}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping)


def parse_workflow(data: Any, *, source: str = "<mapping>") -> WorkflowDefinition:
    """Validate already parsed YAML data, wrapping errors with source context."""
    try:
        return WorkflowDefinition.model_validate(data)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}" for item in exc.errors()
        )
        raise ConfigurationError(f"invalid workflow configuration in {source}: {details}") from exc
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"invalid workflow configuration in {source}: {exc}") from exc


def load_workflow(path: str | Path) -> WorkflowDefinition:
    """Load one safe YAML workflow file into a frozen, validated model."""
    file_path = Path(path)
    try:
        with file_path.open("r", encoding="utf-8") as stream:
            data = yaml.load(stream, Loader=_UniqueKeyLoader)
    except (OSError, yaml.YAMLError, ConfigurationError) as exc:
        raise ConfigurationError(f"could not load workflow {file_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigurationError(f"workflow {file_path} must contain a YAML mapping")
    return parse_workflow(data, source=str(file_path))


def load_workflows(directory: str | Path | None = None) -> Mapping[tuple[str, int], WorkflowDefinition]:
    """Load every YAML workflow under a directory, keyed by immutable workflow/version."""
    config_dir = Path(directory) if directory is not None else Path(__file__).parents[2] / "configs" / "workflows"
    if not config_dir.is_dir():
        raise ConfigurationError(f"workflow configuration directory does not exist: {config_dir}")
    definitions: dict[tuple[str, int], WorkflowDefinition] = {}
    for file_path in sorted((*config_dir.glob("*.yaml"), *config_dir.glob("*.yml"))):
        definition = load_workflow(file_path)
        key = (definition.workflow_id, definition.version)
        if key in definitions:
            raise ConfigurationError(f"duplicate workflow version {key[0]} version {key[1]}")
        definitions[key] = definition
    return MappingProxyType(definitions)
