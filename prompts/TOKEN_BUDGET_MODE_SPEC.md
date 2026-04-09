# Token-Budgeted Arbitration Mode Spec

## Purpose
Add a runtime comparison mode that lets the user set a token budget on the fly and compare arbitration behavior under constraint versus unconstrained execution.

## Core Goal
Enable side-by-side evaluation of:
- arbitrated scoring with no token budget constraint
- arbitrated scoring with a user-specified token budget

This should make reliability and trace quality differences observable when compute is limited.

## Why This Feature
- Current demo compares baseline vs arbitrated, but not constrained vs unconstrained arbitration.
- Real deployments often run under strict token budgets.
- We need a reproducible way to show how arbitration degrades or adapts when budget is tight.

## User Outcomes
- Set token budget at runtime (CLI flag or prompt).
- Run one command to get constrained and unconstrained arbitration results.
- See score deltas, match vs ground truth, and budget usage in one artifact.
- Inspect traces that explicitly show budget effects per step/pass.

## Functional Goals
1. Accept a user-provided token budget at runtime.
2. Apply budget constraints during arbitrated execution.
3. Preserve existing unconstrained arbitration behavior.
4. Produce a single comparison artifact including:
   - ground-truth score
   - unconstrained arbitrated score
   - constrained arbitrated score
   - match flags against ground truth
   - budget usage summary
5. Emit trace metadata that captures budget consumption and remaining allowance.

## Trace and Observability Goals
- Budget state must be explicit in traces.
- Each model call should record:
  - allocated token cap
  - estimated/observed usage
  - remaining budget after call
- Final trace summary should show whether budget was exhausted.

## Correctness Goals
- If budget is sufficient, constrained mode should be able to match unconstrained behavior.
- If budget is exhausted, behavior should be deterministic and observable (not silent failure).
- Parsing and scoring outputs should remain robust even with truncated/limited outputs.

## CLI/UX Goals
- Simple runtime interface such as:
  - `--mode arbitrated_vs_budgeted`
  - `--token-budget <int>`
- If budget is omitted in budgeted mode, fail fast with a clear message or prompt for input.

## Non-Goals (Initial Iteration)
- Provider-specific token accounting guarantees.
- Perfect token counting accuracy across model vendors.
- Multi-model orchestration or adaptive model switching.
- UI/dashboard work beyond terminal artifact and JSON output.

## Definition of Done
- Feature has a documented runtime mode for budgeted arbitration comparison.
- End-to-end run produces constrained vs unconstrained comparison output.
- Trace output includes budget metadata per relevant step.
- Tests cover:
  - budget consumption behavior
  - exhausted-budget behavior
  - comparison artifact fields
