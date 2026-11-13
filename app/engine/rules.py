"""Pure, deterministic evaluator for validated declarative rule sets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.engine.config import Condition, FailureAction, Operator, RuleSet


class RuleEvaluationError(ValueError):
    """Input data cannot be evaluated safely against the configured condition."""


@dataclass(frozen=True, slots=True)
class RuleTrace:
    rule_id: str
    expression_reference: str
    operator: str
    actual_value: Any
    expected_value: Any
    passed: bool
    failure_action: str
    reason: str
    config_version: int

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly representation of this trace entry."""
        return {
            "rule_id": self.rule_id,
            "expression_reference": self.expression_reference,
            "operator": self.operator,
            "actual_value": self.actual_value,
            "expected_value": self.expected_value,
            "passed": self.passed,
            "failure_action": self.failure_action,
            "reason": self.reason,
            "config_version": self.config_version,
        }


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    passed: bool
    outcome: str | None
    traces: tuple[RuleTrace, ...]
    failed_rule_ids: tuple[str, ...]


_MISSING = object()


def _resolve(payload: Mapping[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return _MISSING
        current = current[part]
    return current


def _compatible(actual: Any, expected: Any) -> bool:
    if isinstance(actual, bool) or isinstance(expected, bool):
        return type(actual) is type(expected)
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return True
    return type(actual) is type(expected)


def _evaluate_leaf(condition: Condition, payload: Mapping[str, Any], rule_id: str,
                   action: FailureAction, config_version: int) -> RuleTrace:
    assert condition.field is not None and condition.operator is not None
    actual = _resolve(payload, condition.field)
    expected = condition.value
    op = condition.operator

    if op is Operator.EXISTS:
        exists = actual is not _MISSING
        passed = exists is expected
        actual_value: Any = exists
        reason = "field exists" if exists else "field is missing"
        if passed:
            reason = f"field existence is {str(expected).lower()} as required"
    elif actual is _MISSING:
        actual_value = None
        passed = False
        reason = "required field is missing"
    else:
        actual_value = actual
        candidates = expected if op in (Operator.IN, Operator.NOT_IN) else (expected,)
        for candidate in candidates:
            if not _compatible(actual, candidate):
                raise RuleEvaluationError(
                    f"rule {rule_id!r} field {condition.field!r} has incompatible types: "
                    f"actual {type(actual).__name__}, expected {type(candidate).__name__}"
                )
        try:
            if op is Operator.EQ:
                passed = actual == expected
            elif op is Operator.NE:
                passed = actual != expected
            elif op is Operator.GT:
                passed = actual > expected
            elif op is Operator.GTE:
                passed = actual >= expected
            elif op is Operator.LT:
                passed = actual < expected
            elif op is Operator.LTE:
                passed = actual <= expected
            elif op is Operator.IN:
                passed = actual in expected
            elif op is Operator.NOT_IN:
                passed = actual not in expected
            else:  # Guard against future enum additions without an implementation.
                raise RuleEvaluationError(f"unsupported operator {op.value!r}")
        except TypeError as exc:
            raise RuleEvaluationError(
                f"rule {rule_id!r} cannot apply {op.value} to field {condition.field!r}: {exc}"
            ) from exc
        reason = (
            f"actual value satisfies {op.value} condition"
            if passed
            else f"actual value does not satisfy {op.value} condition"
        )

    return RuleTrace(
        rule_id=rule_id,
        expression_reference=condition.field,
        operator=op.value,
        actual_value=actual_value,
        expected_value=expected,
        passed=passed,
        failure_action=action.value,
        reason=reason,
        config_version=config_version,
    )


def _evaluate_condition(condition: Condition, payload: Mapping[str, Any], rule_id: str,
                        action: FailureAction, config_version: int,
                        traces: list[RuleTrace]) -> bool:
    if condition.field is not None:
        trace = _evaluate_leaf(condition, payload, rule_id, action, config_version)
        traces.append(trace)
        return trace.passed
    if condition.all is not None:
        # Evaluate every branch to produce complete deterministic explanations.
        outcomes = [
            _evaluate_condition(child, payload, rule_id, action, config_version, traces)
            for child in condition.all
        ]
        return all(outcomes)
    assert condition.any is not None
    outcomes = [
        _evaluate_condition(child, payload, rule_id, action, config_version, traces)
        for child in condition.any
    ]
    return any(outcomes)


def evaluate_rules(rule_set: RuleSet, payload: Mapping[str, Any], *,
                   config_version: int) -> EvaluationResult:
    """Evaluate every rule, preserving declaration order and a complete leaf trace.

    Failure precedence is deterministic: REJECT outranks MANUAL_REVIEW, regardless of
    declaration order. All rule conditions are evaluated to retain complete traces.
    """
    if not isinstance(payload, Mapping):
        raise RuleEvaluationError("request payload must be a mapping")
    if config_version < 1:
        raise ValueError("config_version must be a positive integer")

    traces: list[RuleTrace] = []
    failed_actions: list[FailureAction] = []
    failed_ids: list[str] = []
    for rule in rule_set.rules:
        leaf_traces: list[RuleTrace] = []
        passed = _evaluate_condition(
            rule.condition, payload, rule.id, rule.on_failure, config_version, leaf_traces
        )
        traces.extend(leaf_traces)
        if not passed:
            failed_actions.append(rule.on_failure)
            failed_ids.append(rule.id)

    if not failed_actions:
        outcome = None
    elif FailureAction.REJECT in failed_actions:
        outcome = "REJECT"
    else:
        outcome = "MANUAL_REVIEW"
    return EvaluationResult(
        passed=not failed_actions,
        outcome=outcome,
        traces=tuple(traces),
        failed_rule_ids=tuple(failed_ids),
    )
