from __future__ import annotations

from pathlib import Path

import pytest

from app.engine.config import ConfigurationError, load_workflow, load_workflows, parse_workflow
from app.engine.rules import evaluate_rules


CONFIG_DIR = Path(__file__).parents[2] / "configs" / "workflows"


def test_all_examples_load_as_immutable_versioned_definitions():
    workflows = load_workflows(CONFIG_DIR)

    assert set(workflows) == {("loan_approval", 1), ("loan_approval", 2), ("vendor_approval", 1)}
    definition = workflows[("loan_approval", 1)]
    with pytest.raises((AttributeError, TypeError, ValueError)):
        definition.version = 3
    with pytest.raises(TypeError):
        workflows[("loan_approval", 3)] = definition


def test_loan_v1_and_v2_differ_at_credit_score_710():
    workflows = load_workflows(CONFIG_DIR)
    payload = {"applicant": {"age": 35, "monthly_income": 60000, "credit_score": 710}}
    v1 = workflows[("loan_approval", 1)]
    v2 = workflows[("loan_approval", 2)]
    result_v1 = evaluate_rules(v1.rule_sets[0], payload, config_version=v1.version)
    result_v2 = evaluate_rules(v2.rule_sets[0], payload, config_version=v2.version)

    assert result_v1.passed and result_v1.outcome is None
    assert not result_v2.passed and result_v2.outcome == "MANUAL_REVIEW"
    assert result_v2.traces[-1].expected_value == 720


def test_vendor_config_loads_and_evaluates_successfully():
    vendor = load_workflows(CONFIG_DIR)[("vendor_approval", 1)]
    result = evaluate_rules(vendor.rule_sets[0], {
        "vendor": {
            "registration_status": "VALID",
            "compliance": {"tax_clearance": True, "sanctions_clear": True},
            "annual_turnover": 800000,
        }
    }, config_version=vendor.version)
    assert result.passed
    assert [trace.rule_id for trace in result.traces] == [
        "valid_registration", "compliance_checks", "compliance_checks", "minimum_turnover"
    ]


def valid_mapping() -> dict:
    return {
        "workflow_id": "sample", "version": 1, "entry_stage": "entry",
        "rule_sets": [{"id": "rs", "rules": [{"id": "r",
            "condition": {"field": "x", "operator": "eq", "value": 1},
            "on_failure": "REJECT"}]}],
        "stages": [
            {"id": "entry", "type": "RULE_EVALUATION", "rule_set": "rs"},
            {"id": "ok", "type": "TERMINAL", "outcome": "APPROVED"},
            {"id": "no", "type": "TERMINAL", "outcome": "REJECTED"},
            {"id": "review", "type": "TERMINAL", "outcome": "MANUAL_REVIEW"},
        ],
        "transitions": [
            {"from_stage": "entry", "outcome": "SUCCESS", "to_stage": "ok"},
            {"from_stage": "entry", "outcome": "REJECT", "to_stage": "no"},
            {"from_stage": "entry", "outcome": "MANUAL_REVIEW", "to_stage": "review"},
        ],
    }


def test_missing_transition_target_is_descriptive():
    data = valid_mapping()
    data["transitions"][0]["to_stage"] = "missing"
    with pytest.raises(ConfigurationError, match="missing target stage"):
        parse_workflow(data)


def test_missing_entry_stage_is_rejected():
    data = valid_mapping()
    data["entry_stage"] = "missing"
    with pytest.raises(ConfigurationError, match="entry_stage"):
        parse_workflow(data)


def test_unreachable_stage_and_cycle_are_rejected():
    data = valid_mapping()
    data["stages"].append({"id": "orphan", "type": "TERMINAL", "outcome": "APPROVED"})
    with pytest.raises(ConfigurationError, match="unreachable stages"):
        parse_workflow(data)

    data = valid_mapping()
    data["stages"].append({"id": "loop", "type": "HUMAN_TASK"})
    data["transitions"][0]["to_stage"] = "loop"
    data["transitions"].append({"from_stage": "loop", "outcome": "APPROVED", "to_stage": "entry"})
    with pytest.raises(ConfigurationError, match="cycles are unsupported"):
        parse_workflow(data)


def test_duplicate_rule_ids_and_missing_rule_set_are_rejected():
    data = valid_mapping()
    data["rule_sets"][0]["rules"].append(data["rule_sets"][0]["rules"][0].copy())
    with pytest.raises(ConfigurationError, match="duplicate rule id"):
        parse_workflow(data)

    data = valid_mapping()
    data["stages"][0]["rule_set"] = "absent"
    with pytest.raises(ConfigurationError, match="missing rule_set"):
        parse_workflow(data)


def test_malformed_yaml_and_duplicate_yaml_keys_have_descriptive_errors(tmp_path):
    malformed = tmp_path / "broken.yaml"
    malformed.write_text("workflow_id: [unterminated", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="could not load workflow"):
        load_workflow(malformed)

    duplicated = tmp_path / "duplicate.yaml"
    duplicated.write_text("workflow_id: a\nworkflow_id: b\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="duplicate YAML key"):
        load_workflow(duplicated)


def test_trace_contains_pass_fail_and_pinned_configuration_version():
    workflow = load_workflows(CONFIG_DIR)[("loan_approval", 1)]
    result = evaluate_rules(workflow.rule_sets[0], {
        "applicant": {"age": 17, "monthly_income": 25000, "credit_score": 650}
    }, config_version=workflow.version)
    trace = result.traces[0].as_dict()
    assert trace["rule_id"] == "minimum_age"
    assert trace["expression_reference"] == "applicant.age"
    assert trace["operator"] == "gte"
    assert trace["actual_value"] == 17 and trace["expected_value"] == 18
    assert trace["passed"] is False
    assert trace["failure_action"] == "REJECT"
    assert trace["config_version"] == 1
    assert trace["reason"]
