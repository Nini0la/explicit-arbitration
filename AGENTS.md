# AGENTS.md - Explicit Arbitration Project Context

## Project Purpose
Explicit Arbitration is a post-generation decision layer for LLM and agent workflows.

It sits between an upstream producer (LLM, agent, tool, or workflow step) and a downstream destination (user response, tool call, memory write, API action, or next agent).

Its job is to decide whether a candidate output should:
- ALLOW
- REVISE
- BLOCK
- ESCALATE

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
1. Candidate output is produced
2. Arbitration gate evaluates decomposition need
3. If useful, invoke ReasonTree
4. HydraDecide arbitrates:
   - full candidate directly, or
   - node outputs sequentially
5. Return typed verdict

---

## Core Components

### HydraDecide
Responsibilities:
- multi-pass arbitration
- contradiction detection
- correction proposal
- confidence estimation
- final release verdict

### ReasonTree
Responsibilities:
- task decomposition
- dependency ordering
- evaluable subquestions
- explicit node outputs

---

## Implementation Rules
- Prefer typed dataclasses or Pydantic models
- Separate gating from arbitration
- Separate decomposition from verdict aggregation
- Keep verdicts explicit
- Keep traces first-class

---

## Code Style
- pathlib
- type hints everywhere
- small composable functions

---

## Design Bias
- HydraDecide always runs
- ReasonTree only when decomposition helps
- Components must remain provider-agnostic
- Avoid tight coupling to demo logic