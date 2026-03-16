# TEST_PLAN.md

## Build Target

Current minimal build target: `negotiation transcript -> score computation`.

This test plan defines what must be tested before and during implementation of the minimal runnable demo.

## 1. Scope

This plan covers only:

- deterministic scoring
- ReasonTree decomposition
- HydraDecide node refinement
- orchestrated end-to-end execution
- baseline vs arbitrated comparison
- trace emission

Explicitly out of scope for v1:

- router tests
- gate tests

## 2. Test Sections

### Deterministic Scorer Tests

Must test:

- exact score for known sessions
- exact breakdown values (`deal_points`, `price_points`, `turn_points`)
- `no_deal` behavior
- repeatability/determinism for same input
- edge cases (`turns=[]`, `final_price=None` when valid)

Example pytest names:

- `test_compute_ground_truth_score_known_sessions_exact_values`
- `test_compute_ground_truth_score_no_deal_zero_deal_and_price_points`
- `test_compute_ground_truth_score_is_deterministic`
- `test_compute_ground_truth_score_zero_turns`
- `test_compute_ground_truth_score_final_price_none_with_no_deal`

### ReasonTree Tests

Must test:

- valid `TaskInput` returns ordered nodes
- node count is appropriate for multi-step score computation
- node ids are unique
- dependencies only point backward
- `expected_output_type` values are valid
- same input gives same node structure

Example pytest names:

- `test_build_reason_tree_returns_ordered_nodes_for_valid_task`
- `test_build_reason_tree_node_count_for_scoring_task`
- `test_build_reason_tree_node_ids_are_unique`
- `test_build_reason_tree_dependencies_reference_prior_nodes_only`
- `test_build_reason_tree_expected_output_type_is_valid`
- `test_build_reason_tree_is_deterministic_for_same_input`

### HydraDecide Tests

Must test:

- runs configured number of passes
- returns non-empty raw `final_output`
- preserves `node_id`
- records `contradictions` and `revision_notes` fields even if empty
- can use `prior_node_outputs`
- works with a stub `model_call`

Example pytest names:

- `test_run_hydra_for_node_uses_configured_pass_count`
- `test_run_hydra_for_node_returns_non_empty_final_output`
- `test_run_hydra_for_node_preserves_node_id`
- `test_run_hydra_for_node_includes_contradictions_and_revision_notes_fields`
- `test_run_hydra_for_node_receives_prior_node_outputs`
- `test_run_hydra_for_node_with_stub_model_call`

### Orchestrator Tests

Must test:

- executes nodes in order
- passes prior node outputs forward
- returns `ScoreResult` plus trace bundle
- final score is parsed from final raw node output
- fails observably if final output is unparsable

Example pytest names:

- `test_run_arbitrated_executes_nodes_in_reason_tree_order`
- `test_run_arbitrated_threads_prior_node_outputs`
- `test_run_arbitrated_returns_score_result_and_trace_bundle`
- `test_run_arbitrated_parses_final_score_from_last_node_output`
- `test_run_arbitrated_raises_or_returns_error_on_unparseable_final_output`

### Trace Tests

Must test:

- trace list is non-empty
- trace entries include `run_id`, `component`, `step`, `timestamp_utc`
- major steps are represented (`reasontree`, hydra pass events, orchestrator finalization)
- Hydra passes produce traceable entries
- same run shares same `run_id`

Example pytest names:

- `test_arbitrated_trace_bundle_is_non_empty`
- `test_trace_entry_includes_required_fields`
- `test_trace_includes_major_components_and_steps`
- `test_hydra_passes_emit_trace_entries`
- `test_single_run_uses_single_run_id_across_entries`

### Baseline Runner Tests

Must test:

- runs on same `TaskInput` as arbitrated path
- returns parseable score output
- does not depend on ReasonTree/HydraDecide internals

Example pytest names:

- `test_run_baseline_accepts_same_task_input_as_arbitrated`
- `test_run_baseline_returns_parseable_score_result`
- `test_run_baseline_does_not_call_reasontree_or_hydra`

### End-to-End Demo Tests

Must test:

- one sample session runs through ground truth, baseline, and arbitrated paths
- output comparison artifact can be produced
- at least two deterministic sample sessions exist
- sample sessions are selected to make divergence plausible, not guaranteed

Example pytest names:

- `test_demo_session_runs_ground_truth_baseline_and_arbitrated`
- `test_demo_produces_comparison_artifact`
- `test_sample_sessions_minimum_count_and_determinism`
- `test_sample_sessions_support_plausible_divergence_scenarios`

## 3. Test Style Guidance

- use `pytest`
- prefer small deterministic fixtures
- use stub/fake `model_call` functions rather than real provider calls
- avoid flaky tests
- avoid tests that require a real LLM API

## 4. Proposed Test Files

- `tests/test_scoring_rules.py`
- `tests/test_reasontree.py`
- `tests/test_hydradecide.py`
- `tests/test_orchestrator.py`
- `tests/test_traces.py`
- `tests/test_baseline_runner.py`
- `tests/test_end_to_end.py`

## 5. Test Data

Require a small deterministic set of sample negotiation sessions.

Requirements:

- at least 2 sessions in `sample_sessions.py`
- each session has known expected ground-truth score and breakdown in advance
- test fixtures use these fixed expected values directly
- sessions should represent varied outcomes (for example, deal and no_deal) while remaining deterministic

## 6. Acceptance Criteria (v1)

Minimum conditions that must pass before v1 is considered complete:

1. All tests in Sections 2-5 pass under `uv run pytest`.
2. Deterministic scorer tests assert exact score and exact breakdown values for known sessions.
3. ReasonTree tests confirm deterministic ordered decomposition with valid backward-only dependencies.
4. HydraDecide tests confirm pass count behavior, non-empty final output, and required result fields.
5. Orchestrator tests confirm ordered execution, forward threading of node outputs, and observable failure on unparseable final output.
6. Trace tests confirm non-empty trace bundles with required fields and consistent `run_id` per run.
7. Baseline tests confirm same input compatibility and parseable output without ReasonTree/HydraDecide coupling.
8. End-to-end tests confirm one-command flow coverage for ground truth, baseline, and arbitrated outputs plus comparison artifact.
9. No router/gate tests are included in v1 test suite.
