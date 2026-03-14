# AGENTS.md - Explicit Arbitration Project Context

## Project Purpose
Explicit Arbitration is a structured execution layer for LLM tasks.

It routes a task through explicit multi-step reasoning so that output production is observable, decomposable, and refinable.

The current implementation focuses on:
- ReasonTree for ordered task decomposition
- HydraDecide for sequential refinement
- full trace emission across execution

The goal is to improve reliability for multi-step tasks while keeping internal reasoning externally inspectable.

---

---

## Current Priority
Build one end-to-end runnable arbitration path in terminal first.

Do not optimize architecture before:
- one ReasonTree decomposition works
- one HydraDecide refinement chain works
- one full terminal run returns final output
- one trace is emitted

---

## Environment
- Python 3.11+
- Use `uv run <command>`
- Dependencies managed via uv only

---

## Repo Layout
- `src/explicit_arbitration/` → core library
- `tests/` → pytest suite
- `examples/` → runnable demos

---

## Development Workflow
1. Create or update PLAN.md before major changes
2. Keep first implementation minimal
3. Run:
   `uv run pytest`
4. Run:
   `uv run ruff check .`

---

## Core Architectural Principle
HydraDecide is the universal arbitration core.
ReasonTree is conditional.

---

## Decision Flow
1. Receive task
2. Build ordered ReasonTree nodes when decomposition is needed for the task
3. Run HydraDecide sequentially across node prompts or directly on the task when decomposition is skipped
4. Pass node outputs forward when dependencies exist
5. Return the final output from the last refinement step

---

---

## Core Components

### HydraDecide
Responsibilities:
- multi-pass refinement
- contradiction detection
- correction proposal
- intermediate output logging
- final node output generation

### ReasonTree
Responsibilities:
- task decomposition
- dependency ordering
- evaluable subquestions
- explicit node outputs

---

## Implementation Rules
- Prefer typed dataclasses or Pydantic models
- Separate decomposition from refinement
- Keep traces first-class
- Prefer minimal runnable paths before expanding abstractions

---

## Code Style
- pathlib
- type hints everywhere
- small composable functions

---

## Design Bias
- HydraDecide always runs
- ReasonTree is the default for clearly multi-step demo tasks
- Components must remain provider-agnostic
- Avoid tight coupling to demo logic