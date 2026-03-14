# SPEC.md

## 1. System Scope

This build covers one target only:

- Input: a negotiation transcript (or equivalent structured session data)
- Task: compute a negotiation score
- Output: score result from:
  - baseline direct model path
  - arbitrated ReasonTree -> HydraDecide path
  - deterministic ground-truth scorer

Out of scope for this spec:

- product-level roadmap
- generalized agent runtime
- multi-agent orchestration
- UI/web interfaces

### Testable conditions

- A single command can run one session through baseline, arbitrated, and deterministic scorer.
- All three outputs are produced in one run artifact.

---

## 2. Exact Engine Components

### 2.1 ReasonTree

Responsibility:

- Convert `TaskInput` into an ordered list of decomposed scoring subtasks.
- Encode dependency order for sequential execution.

Input:

- `TaskInput`

Output:

- `list[ReasonTreeNode]` (ordered)

Minimal callable interface:

```python
def build_reason_tree(task: TaskInput) -> list[ReasonTreeNode]:
    ...
```

Must not do:

- Call LLM/provider APIs
- Compute final score
- Execute node prompts

### Testable conditions

- For a valid `TaskInput`, returns at least 1 node.
- Node order is deterministic for the same input.
- Each non-root node dependency references an earlier node id.

---

### 2.2 HydraDecide

Responsibility:

- Execute multi-pass refinement for a single node prompt.
- Detect contradictions across passes.
- Produce final node output and confidence.

Input:

- `ReasonTreeNode`
- `TaskInput`
- `prior_node_outputs: dict[str, object]`
- `model_call: Callable[[str], str]`

Output:

- `HydraResult`

Minimal callable interface:

```python
from collections.abc import Callable

def run_hydra_for_node(
    node: ReasonTreeNode,
    task: TaskInput,
    prior_node_outputs: dict[str, object],
    model_call: Callable[[str], str],
    passes: int = 2,
) -> HydraResult:
    ...
```

Must not do:

- Build ReasonTree nodes
- Reorder execution
- Decide whether to run decomposition (always decomposed in this version)

### Testable conditions

- Runs at least 2 passes by default.
- Returns `HydraResult.pass_count == passes`.
- Returns a non-empty `final_output`.

---

### 2.3 Orchestrator

Responsibility:

- Execute the end-to-end arbitrated flow deterministically:
  1. build ReasonTree
  2. run HydraDecide for each node in order
  3. thread node outputs forward
  4. return final score result + trace bundle

Input:

- `TaskInput`
- `model_call: Callable[[str], str]`

Output:

- `tuple[ScoreResult, list[TraceEntry]]`

Minimal callable interface:

```python
from collections.abc import Callable

def run_arbitrated(
    task: TaskInput,
    model_call: Callable[[str], str],
) -> tuple[ScoreResult, list[TraceEntry]]:
    ...
```

Must not do:

- Add routing logic (no router in current version)
- Invoke baseline path internally

### Testable conditions

- Node execution count equals ReasonTree node count.
- Final score is derived from the final node output.
- Trace bundle includes entries for each major step.

---

### 2.4 Trace Logging

Responsibility:

- Record structured events for ReasonTree, Hydra passes, and orchestration milestones.
- Return all entries for one run as an in-memory bundle.

Input:

- component name
- step name
- structured input payload
- structured output payload
- optional metadata

Output:

- appended `TraceEntry`
- trace bundle: `list[TraceEntry]`

Minimal callable interface:

```python
def record_trace(
    store: list[TraceEntry],
    entry: TraceEntry,
) -> None:
    ...

def new_trace_entry(
    run_id: str,
    component: str,
    step: str,
    input_payload: dict[str, object],
    output_payload: dict[str, object],
    metadata: dict[str, object] | None = None,
) -> TraceEntry:
    ...
```

Must not do:

- Persist to external DB/files by default
- Mutate scoring decisions

### Testable conditions

- Every run returns a non-empty trace list.
- Trace entries contain `run_id`, `component`, `step`, timestamp.

---

### 2.5 Deterministic Scorer

Responsibility:

- Compute objective score from structured session fields using fixed code rules.
- Provide score breakdown used as ground truth in tests.

Input:

- structured negotiation session fields (defined in Section 5)

Output:

- `ScoreResult`

Minimal callable interface:

```python
def compute_ground_truth_score(session: NegotiationSession) -> ScoreResult:
    ...
```

Must not do:

- Call LLM/provider APIs
- Use nondeterministic randomness/time-dependent behavior

### Testable conditions

- Same input session always returns same score and breakdown.
- Known sample sessions match fixed expected numeric scores.

---

### 2.6 Baseline Runner

Responsibility:

- Run direct single-model score computation on the same `TaskInput`.

Input:

- `TaskInput`
- `model_call: Callable[[str], str]`

Output:

- `ScoreResult`

Minimal callable interface:

```python
from collections.abc import Callable

def run_baseline(
    task: TaskInput,
    model_call: Callable[[str], str],
) -> ScoreResult:
    ...
```

Must not do:

- Use ReasonTree or HydraDecide internals
- Emit arbitrated node-level traces

### Testable conditions

- Baseline runs on same task input used by arbitrated path.
- Baseline returns parseable score output.

---

## 3. Core Data Structures

Required shapes (Python dataclasses or Pydantic models; dataclasses preferred for minimal build):

```python
from dataclasses import dataclass, field
from typing import Literal, Any

@dataclass(slots=True)
class NegotiationTurn:
    turn_index: int
    speaker: Literal["buyer", "seller"]
    message: str
    offer_price: float | None

@dataclass(slots=True)
class NegotiationSession:
    session_id: str
    item_name: str
    reference_price: float
    turns: list[NegotiationTurn]
    outcome: Literal["deal", "no_deal"]
    final_price: float | None

@dataclass(slots=True)
class TaskInput:
    task_id: str
    instruction: str
    session: NegotiationSession
    require_explanation: bool = False

@dataclass(slots=True)
class ReasonTreeNode:
    node_id: str
    purpose: str
    prompt: str
    depends_on: list[str]
    expected_output_type: Literal["facts", "pricing_eval", "turn_eval", "final_score"]

@dataclass(slots=True)
class HydraResult:
    node_id: str
    pass_count: int
    pass_outputs: list[str]
    contradictions: list[str]
    revision_notes: list[str]
    final_output: str
    confidence: float

@dataclass(slots=True)
class TraceEntry:
    run_id: str
    timestamp_utc: str
    component: Literal["reasontree", "hydradecide", "orchestrator", "baseline", "scoring"]
    step: str
    input_payload: dict[str, Any]
    output_payload: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(slots=True)
class ScoreResult:
    score: int
    breakdown: dict[str, int]
    explanation: str | None
```

### Testable conditions

- Type checks/static checks pass for all required fields.
- Object construction fails when required fields are missing.

---

## 4. End-to-End Execution Contract

Runtime flow for current version (no router):

1. Receive `TaskInput`.
2. Call `build_reason_tree(task)` to produce ordered nodes.
3. Initialize `node_outputs = {}` and `trace_entries = []`.
4. For each node in order:
   - Call `run_hydra_for_node(node, task, node_outputs, model_call)`.
   - Store result in `node_outputs[node.node_id] = hydra_result.final_output`.
   - Append trace entries for each Hydra pass and node finalization.
5. Parse the final node output into numeric score and explanation.
6. Return `ScoreResult` and full `trace_entries`.

### Testable conditions

- Execution order equals node order returned by ReasonTree.
- Downstream nodes can access prior node outputs.
- Final return object includes both `ScoreResult` and full trace bundle.

---

## 5. Deterministic Scoring Contract

### 5.1 Required transcript/session fields

- `session_id: str`
- `item_name: str`
- `reference_price: float`
- `turns: list[NegotiationTurn]`
  - each turn has:
    - `turn_index: int`
    - `speaker: "buyer" | "seller"`
    - `message: str`
    - `offer_price: float | None`
- `outcome: "deal" | "no_deal"`
- `final_price: float | None`

### 5.2 Deterministic score formula (0 to 100)

If `outcome == "no_deal"` or `final_price is None`:

- `deal_points = 0`
- `price_points = 0`

Else:

- `deal_points = 20`
- `savings_ratio = max(0.0, min(1.0, (reference_price - final_price) / reference_price))`
- `price_points = round(60 * savings_ratio)`

Turn efficiency points:

- `turn_count = len(turns)`
- `turn_points = max(0, 20 - max(0, turn_count - 2) * 2)`

Final score:

- `score = deal_points + price_points + turn_points`
- clamp to `[0, 100]`

Breakdown keys required:

- `deal_points`
- `price_points`
- `turn_points`

### 5.3 Ground truth definition

Ground truth is the output of `compute_ground_truth_score(session)` using only the rules above.  
No model output is part of ground truth.

### 5.4 Test assertion contract

Tests must assert:

- exact integer `score`
- exact `breakdown` values
- deterministic repeatability (same input -> same output)

### Testable conditions

- Parametrized tests over sample sessions pass with fixed expected values.
- Any change to formula causes expected-test failure.

---

## 6. Minimal Module Mapping

Required files and required symbols:

- `reasontree.py`
  - `build_reason_tree(task: TaskInput) -> list[ReasonTreeNode]`
- `hydradecide.py`
  - `run_hydra_for_node(...) -> HydraResult`
- `orchestrator.py`
  - `run_arbitrated(task, model_call) -> tuple[ScoreResult, list[TraceEntry]]`
- `traces.py`
  - `new_trace_entry(...) -> TraceEntry`
  - `record_trace(store, entry) -> None`
- `scoring_rules.py`
  - `compute_ground_truth_score(session) -> ScoreResult`
- `baseline_runner.py`
  - `run_baseline(task, model_call) -> ScoreResult`
- `arbitrated_runner.py`
  - CLI/script entry that calls orchestrator and prints:
    - ground truth
    - baseline score
    - arbitrated score
    - match flags
    - trace summary
- `sample_sessions.py`
  - at least 2 deterministic sample sessions with expected ground-truth scores

### Testable conditions

- Imports for all required symbols succeed.
- `arbitrated_runner.py` executes end-to-end from terminal.

---

## 7. Testable Success Conditions

Minimum acceptance criteria for this spec:

1. One negotiation session runs end-to-end via one command.
2. Baseline path returns a score.
3. Arbitrated path returns a score.
4. Deterministic scorer returns ground truth.
5. Output shows baseline vs arbitrated vs ground truth in same run.
6. Arbitrated run returns non-empty trace bundle with node-level entries.
7. At least one sample session is expected to show baseline mismatch while arbitrated matches ground truth (or closer absolute error).

---

## 8. Constraints

- Keep implementation minimal and directly tied to current scoring demo.
- Avoid speculative abstractions and framework-heavy layering.
- Avoid future multi-agent expansion in code or spec.
- Avoid UI feature discussion; terminal output only.

### Testable conditions

- No module introduces unrelated product features.
- No router logic is required for current execution path.
