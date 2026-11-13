from __future__ import annotations

import pytest

from app.engine.config import ConfigurationError, Rule, RuleSet, parse_workflow
from app.engine.rules import RuleEvaluationError, evaluate_rules


def make_rule_set(condition: dict, *, action: str = "REJECT") -> RuleSet:
    return RuleSet.model_validate({
        "id": "test",
        "rules": [{"id": "rule-1", "condition": condition, "on_failure": action}],
    })


@pytest.mark.parametrize(
    ("operator", "actual", "expected", "passed"),
    [
        ("eq", 4, 4, True), ("ne", 4, 3, True), ("gt", 4, 3, True),
        ("gte", 4, 4, True), ("lt", 3, 4, True), ("lte", 4, 4, True),
        ("in", "b", ["a", "b"], True), ("not_in", "c", ["a", "b"], True),
        ("exists", 1, True, True), ("exists", None, False, False),
    ],
)
def test_supported_operators(operator, actual, expected, passed):
    condition = {"field": "applicant.score", "operator": operator, "value": expected}
    result = evaluate_rules(make_rule_set(condition), {"applicant": {"score": actual}}, config_version=3)

    assert result.passed is passed
    assert result.traces[0].operator == operator
    assert result.traces[0].config_version == 3


def test_nested_all_any_conditions_evaluate_all_leaves_and_trace_them():
    conditions = {
        "all": [
            {"field": "applicant.age", "operator": "gte", "value": 18},
            {"any": [
                {"field": "applicant.country", "operator": "eq", "value": "IN"},
                {"field": "applicant.score", "operator": "gte", "value": 700},
            ]},
        ]
    }
    result = evaluate_rules(
        make_rule_set(conditions),
        {"applicant": {"age": 21, "country": "US", "score": 720}},
        config_version=7,
    )

    assert result.passed
    assert [trace.expression_reference for trace in result.traces] == [
        "applicant.age", "applicant.country", "applicant.score"
    ]
    assert result.traces[1].passed is False
    assert result.traces[2].passed is True


def test_threshold_failure_has_explanation_and_configured_action():
    result = evaluate_rules(
        make_rule_set({"field": "applicant.age", "operator": "gte", "value": 18}, action="REJECT"),
        {"applicant": {"age": 17}}, config_version=1,
    )

    trace = result.traces[0]
    assert not result.passed and result.outcome == "REJECT"
    assert trace.rule_id == "rule-1"
    assert trace.actual_value == 17 and trace.expected_value == 18
    assert trace.failure_action == "REJECT" and trace.config_version == 1
    assert "does not satisfy" in trace.reason


def test_missing_comparison_field_fails_explicitly_and_exists_can_check_absence():
    missing_required = evaluate_rules(
        make_rule_set({"field": "applicant.age", "operator": "gte", "value": 18}),
        {"applicant": {}}, config_version=1,
    )
    assert not missing_required.passed
    assert missing_required.traces[0].actual_value is None
    assert "missing" in missing_required.traces[0].reason

    optional_absence = evaluate_rules(
        make_rule_set({"field": "applicant.nickname", "operator": "exists", "value": False}),
        {"applicant": {}}, config_version=1,
    )
    assert optional_absence.passed
    assert optional_absence.traces[0].actual_value is False


def test_incompatible_comparison_types_raise_instead_of_becoming_a_decision():
    with pytest.raises(RuleEvaluationError, match="incompatible types"):
        evaluate_rules(
            make_rule_set({"field": "applicant.age", "operator": "gte", "value": 18}),
            {"applicant": {"age": "18"}}, config_version=1,
        )


def test_reject_has_precedence_over_manual_review_and_declaration_order_is_stable():
    rule_set = RuleSet.model_validate({
        "id": "precedence",
        "rules": [
            {"id": "review", "condition": {"field": "x", "operator": "eq", "value": 1},
             "on_failure": "MANUAL_REVIEW"},
            {"id": "reject", "condition": {"field": "y", "operator": "eq", "value": 1},
             "on_failure": "REJECT"},
        ],
    })
    result = evaluate_rules(rule_set, {"x": 0, "y": 0}, config_version=1)
    assert result.outcome == "REJECT"
    assert result.failed_rule_ids == ("review", "reject")


def test_invalid_operator_is_rejected_during_config_validation():
    with pytest.raises(ConfigurationError, match="operator"):
        parse_workflow({
            "workflow_id": "bad", "version": 1, "entry_stage": "entry",
            "rule_sets": [{"id": "rs", "rules": [{"id": "r",
                "condition": {"field": "x", "operator": "approx", "value": 1},
                "on_failure": "REJECT"}]}],
            "stages": [
                {"id": "entry", "type": "RULE_EVALUATION", "rule_set": "rs"},
                {"id": "a", "type": "TERMINAL", "outcome": "APPROVED"},
                {"id": "rj", "type": "TERMINAL", "outcome": "REJECTED"},
                {"id": "mr", "type": "TERMINAL", "outcome": "MANUAL_REVIEW"},
            ],
            "transitions": [
                {"from_stage": "entry", "outcome": "SUCCESS", "to_stage": "a"},
                {"from_stage": "entry", "outcome": "REJECT", "to_stage": "rj"},
                {"from_stage": "entry", "outcome": "MANUAL_REVIEW", "to_stage": "mr"},
            ],
        })


def test_empty_nested_group_is_rejected():
    with pytest.raises(Exception, match="must not be empty"):
        make_rule_set({"all": []})
