# PLAN.md

## Project Goal

Build a minimal runnable arbitration engine for the ACM demo, using negotiation transcript → score computation as the proving task, then compare:

1. **Baseline path**: one model computes the user’s score directly from the negotiation transcript.
2. **Arbitrated path**: ReasonTree → HydraDecide computes the same score with full trace logs.

The core claim of the demo is:

> Explicit arbitration improves reliability and observability for multi-step scoring tasks in an LLM-driven negotiation setting.

---

## Primary Deliverable

A terminal-runnable demo where:

- a negotiation transcript or structured session is provided
- a scoring task is executed in two modes:
  - baseline single-model mode
  - arbitrated mode
- both outputs are compared against a deterministic ground-truth scorer
- full traces are emitted for the arbitrated path
- divergence between baseline and arbitrated outputs is visible

---

## Repo Strategy

Use **one repo** with **strict separation** between:

- **engine/kernel layer**: reusable arbitration system
- **demo layer**: negotiation transcript inputs and score-computation comparison

The demo depends on the engine.  
The engine must not depend on store-specific logic.

---

## Execution Phases

### Phase 1 — Define the core engine interfaces

Implement the minimal architecture for:

- ReasonTree
- HydraDecide
- Orchestrator
- Trace logging structures

This phase focuses on the shape of the system, not prompt tuning.

**Done when:**
- the engine can accept a task input
- ReasonTree can produce ordered nodes
- HydraDecide can refine node outputs
- traces are captured for every step

---

### Phase 2 — Define deterministic store scoring ground truth

Implement a deterministic code-based scorer for negotiation sessions.

This scorer becomes the evaluation reference.

Possible score inputs:

- true item price
- final agreed price or no-deal
- number of turns taken
- whether the user negotiated efficiently
- whether the final result is favorable relative to the reference price

**Done when:**
- a structured negotiation session can be passed into code
- the scorer returns a deterministic score
- expected scores can be asserted in tests

---

### Phase 3 — Build the demo scoring task

Create the score-computation task that both baseline and arbitrated modes will attempt.

Input:
- negotiation transcript or structured interaction history
- scoring instruction / rubric

Output:
- computed score
- optional explanation
- trace/log artifacts

This is the core task used in the demo.

**Done when:**
- the same task can run in both baseline and arbitrated modes
- both outputs can be compared against ground truth

---

### Phase 4 — Optional direct-path support

Allow HydraDecide-only execution for simple tasks when decomposition is unnecessary.

For the current demo, negotiation score computation is treated as decomposition-worthy by default, so direct-path support is secondary.

**Done when:**
- HydraDecide can run on a task without ReasonTree when needed
- the direct path can return final output
- traces remain consistent across both paths

---

### Phase 5 — Build ReasonTree decomposition

Implement ReasonTree as a structured decomposition step that produces ordered dependent nodes.

Each node should contain:

- node id
- subtask purpose
- node prompt
- dependency information
- expected output type

For the demo, ReasonTree should decompose multi-step score computation into sequential subtasks.

Example shape:
- identify relevant negotiation facts
- determine pricing relationship
- count turns / penalties
- compute final score

**Done when:**
- complex tasks produce an ordered node list
- node outputs can feed later nodes
- traces record prompts and outputs for every node

---

### Phase 6 — Build HydraDecide refinement

Implement HydraDecide as a sequential refinement/arbitration component.

HydraDecide should:
- take a prompt or node task
- perform at least two refinement passes
- produce a final node result
- emit internal trace logs

For the current demo, HydraDecide primarily runs per node after ReasonTree decomposition. Direct task refinement is optional future support.

**Done when:**
- a task can be refined through multiple internal passes
- the final output is available to the orchestrator
- all intermediate prompts and outputs are logged

---

### Phase 7 — Build orchestration flow

Implement the top-level engine flow:

1. receive task
2. build ReasonTree nodes
3. run HydraDecide on each node in sequence
4. pass node outputs forward
5. return final output from the last node’s final HydraDecide output

For the current demo, multi-step score tasks may enter ReasonTree directly without a separate routing call.
## Current Demo Assumption

For the current ACM demo, negotiation transcript → score computation is treated as a clearly multi-step task and enters ReasonTree directly.

A separate routing call is optional future work.

---

**Done when:**
- one end-to-end run works in terminal
- both routes are supported
- traces are emitted throughout the run

---

### Phase 8 — Build baseline runner

Implement a single-model baseline runner.

The baseline should:
- receive the same input task
- receive the same scoring instructions
- produce a score directly
- optionally log its own raw prompt and output

This provides the comparison target.

**Done when:**
- baseline and arbitrated systems can run on the same session
- outputs can be compared side by side

---

### Phase 9 — Demo output and comparison view

Create a simple terminal display for:

- session input
- ground-truth score
- baseline score
- arbitrated score
- whether each matched ground truth
- arbitrated trace summary

This should be optimized for a quick demo, not full UI polish.

**Done when:**
- one command runs the demo
- results are human-readable
- divergence is obvious

---

## Minimal Success Criteria

The minimal demo is successful if:

- one negotiation session can be scored end-to-end
- baseline and arbitrated paths both run
- the arbitrated path emits full observable traces
- at least one example shows meaningful divergence or improved reliability
- the deterministic scorer provides objective evaluation

---

## Non-Goals for This Iteration

## V1 Implementation Plan (Current)

1. Implement deterministic scorer (`scoring_rules.py`) from `SPEC.md` formula.
2. Add deterministic sample sessions + expected ground-truth scores (`sample_sessions.py`).
3. Implement deterministic ReasonTree decomposition (`reasontree.py`).
4. Implement stub-compatible HydraDecide multi-pass runner (`hydradecide.py`).
5. Implement minimal trace entry creation and append helpers (`traces.py`).
6. Implement arbitrated orchestrator flow with explicit final score parsing (`orchestrator.py`).
7. Implement baseline direct runner with no ReasonTree/Hydra coupling (`baseline_runner.py`).
8. Implement terminal runnable comparison script (`arbitrated_runner.py`).
9. Run `uv run pytest` progressively and fix failures until passing.

These are explicitly out of scope unless time remains:

- full conversational store agent
- persistent memory
- multi-user gameplay system
- sophisticated UI
- generalized commerce reasoning
- production-grade agent infrastructure
- extensive prompt optimization

The goal is not a complete shopkeeper bot.  
The goal is a **clear arbitration demo**.

---

## Implementation Order

1. Define data models
2. Implement deterministic scorer
3. Implement ReasonTree
4. Implement HydraDecide
5. Implement orchestrator
6. Implement baseline runner
7. Create sample negotiation sessions
8. Run comparisons and capture traces
9. Add optional direct-path support if time remains

---

## Required Files

- `PLAN.md`
- `SPEC.md`
- `TEST_PLAN.md`
- `README.md`

Suggested code modules:

- `reasontree.py`
- `hydradecide.py`
- `orchestrator.py`
- `traces.py`
- `scoring_rules.py`
- `baseline_runner.py`
- `arbitrated_runner.py`
- `sample_sessions.py`

---

## Final Definition of Done

The project is done for the ACM demo when:

- a single command runs the demo
- the demo shows baseline vs arbitrated scoring
- a deterministic scorer provides ground truth
- arbitration traces are visible
- the system is minimal, understandable, and reproducible
