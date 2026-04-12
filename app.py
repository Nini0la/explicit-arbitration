from __future__ import annotations

import json
from dataclasses import asdict, dataclass, is_dataclass
from typing import Callable

import streamlit as st

from explicit_arbitration.baseline_runner import run_baseline
from explicit_arbitration.model_client import (
    call_openai_compatible,
    load_live_model_config,
)
from explicit_arbitration.orchestrator import run_arbitrated
from explicit_arbitration.sample_sessions import get_sample_sessions
from explicit_arbitration.scoring_rules import compute_ground_truth_score


@dataclass(slots=True)
class TaskInput:
    task_id: str
    instruction: str
    session: object
    require_explanation: bool = True


def _field(obj: object, name: str):
    if isinstance(obj, dict):
        return obj[name]
    return getattr(obj, name)


def _stub_model_call(_: str) -> str:
    return (
        '{"score": 61, "breakdown": {"deal_points": 20, '
        '"price_points": 21, "turn_points": 20}, "explanation": "stub"}'
    )


def _repair_prompt_for_json(raw_output: str) -> str:
    return (
        "Your previous output was not valid JSON for the required schema. "
        "Return strict JSON only with keys: score, breakdown, explanation.\n"
        f"previous_output={raw_output}"
    )


def _build_model_call(
    use_live_model: bool,
    model: str | None = None,
    max_tokens: int = 300,
    temperature: float = 0.0,
) -> tuple[Callable[[str], str], dict[str, object]]:
    if not use_live_model:
        return _stub_model_call, {"mode": "stub"}

    config = load_live_model_config(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
    )

    def _live_model_call(prompt: str) -> str:
        first = call_openai_compatible(prompt, config)
        try:
            json.loads(first)
            return first
        except json.JSONDecodeError:
            repaired = call_openai_compatible(_repair_prompt_for_json(first), config)
            return repaired

    return _live_model_call, {
        "mode": "live",
        "provider": "openai_compatible_chat_completions",
        "model": config.model,
        "base_url": config.base_url,
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
    }


def _to_primitive(value: object) -> object:
    if is_dataclass(value):
        return {k: _to_primitive(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): _to_primitive(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_primitive(v) for v in value]
    return value


def _serialize_trace_entry(entry: object) -> dict[str, object]:
    return {
        "run_id": str(_field(entry, "run_id")),
        "timestamp_utc": str(_field(entry, "timestamp_utc")),
        "component": str(_field(entry, "component")),
        "step": str(_field(entry, "step")),
        "input_payload": _to_primitive(_field(entry, "input_payload")),
        "output_payload": _to_primitive(_field(entry, "output_payload")),
        "metadata": _to_primitive(_field(entry, "metadata")),
    }


def _build_trace_summary(trace_bundle: list[object]) -> dict[str, object]:
    reason_tree_nodes = 0
    node_sequence: list[str] = []
    hydra_pass_count = 0
    final_node_output: str | None = None

    for entry in trace_bundle:
        component = str(_field(entry, "component"))
        step = str(_field(entry, "step"))
        output_payload = _field(entry, "output_payload")
        input_payload = _field(entry, "input_payload")

        if component == "reasontree" and step == "build_reason_tree":
            node_count = output_payload.get("node_count", 0)
            reason_tree_nodes = int(node_count)
            node_ids = output_payload.get("node_ids", [])
            node_sequence = [str(node_id) for node_id in node_ids]

        if component == "hydradecide" and step == "hydra_pass":
            hydra_pass_count += 1

        if component == "hydradecide" and step == "node_finalized":
            node_id = str(input_payload.get("node_id", ""))
            if node_id == "node-final" or not final_node_output:
                final_node_output = str(output_payload.get("final_output", ""))

    return {
        "reason_tree_node_count": reason_tree_nodes,
        "reason_tree_node_sequence": node_sequence,
        "hydra_pass_count": hydra_pass_count,
        "final_node_output": final_node_output,
    }


def _session_turns(session: object) -> list[dict[str, object]]:
    turns = _field(session, "turns")
    result: list[dict[str, object]] = []
    for turn in turns:
        result.append(
            {
                "turn_index": int(_field(turn, "turn_index")),
                "speaker": str(_field(turn, "speaker")),
                "message": str(_field(turn, "message")),
                "offer_price": _field(turn, "offer_price"),
            }
        )
    return result


def _run_for_session(
    session: object,
    use_live_model: bool,
    model: str | None = None,
    max_tokens: int = 300,
    temperature: float = 0.0,
) -> dict[str, object]:
    task = TaskInput(
        task_id=f"task-{_field(session, 'session_id')}",
        instruction="Score this negotiation session.",
        session=session,
        require_explanation=True,
    )
    model_call, model_mode = _build_model_call(
        use_live_model=use_live_model,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    ground_truth = compute_ground_truth_score(task.session)
    baseline = run_baseline(task, model_call)
    arbitrated, trace_bundle = run_arbitrated(task, model_call)
    serialized_trace = [_serialize_trace_entry(entry) for entry in trace_bundle]
    trace_summary = _build_trace_summary(trace_bundle)

    return {
        "session_id": _field(session, "session_id"),
        "task_id": task.task_id,
        "model_mode": model_mode,
        "ground_truth_score": ground_truth.score,
        "baseline_score": baseline.score,
        "arbitrated_score": arbitrated.score,
        "baseline_match": baseline.score == ground_truth.score,
        "arbitrated_match": arbitrated.score == ground_truth.score,
        "trace_entry_count": len(trace_bundle),
        "session_turns": _session_turns(session),
        "arbitration_trace_summary": trace_summary,
        "arbitration_trace_entries": serialized_trace,
    }


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
          --bg: #f5efe4;
          --panel: #fffdf8;
          --ink: #1b1b1b;
          --muted: #5d615d;
          --accent: #136f63;
        }
        .stApp { background: linear-gradient(120deg, #f5efe4 0%, #e8f2ed 100%); }
        html, body, [class*="css"]  {
          font-family: "Avenir Next", "Trebuchet MS", "Segoe UI", sans-serif;
          color: var(--ink);
        }
        .hero {
          background: var(--panel);
          border: 1px solid #d8d2c7;
          border-left: 8px solid var(--accent);
          border-radius: 14px;
          padding: 1rem 1.2rem;
          margin-bottom: 1rem;
        }
        .hero h1 { margin: 0; font-size: 1.6rem; }
        .hero p { color: var(--muted); margin: 0.35rem 0 0 0; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="Arbitration Console",
        page_icon="",
        layout="wide",
    )
    _inject_styles()

    st.markdown(
        """
        <div class="hero">
          <h1>Explicit Arbitration Console</h1>
          <p>Compare deterministic ground truth, baseline model output, and
          ReasonTree + HydraDecide output with full trace transparency.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    sessions = get_sample_sessions()
    session_map = {str(_field(s, "session_id")): s for s in sessions}

    with st.sidebar:
        st.header("Run Config")
        selected_session_id = st.selectbox(
            "Session",
            options=list(session_map.keys()),
        )
        use_live_model = st.toggle("Use Live Model", value=False)
        model_name = st.text_input("Model", value="gpt-4.1-mini")
        max_tokens = st.number_input(
            "Max Tokens / Call",
            min_value=50,
            max_value=4000,
            value=300,
            step=50,
        )
        temperature = st.slider(
            "Temperature",
            min_value=0.0,
            max_value=1.0,
            value=0.0,
            step=0.1,
        )
        run_clicked = st.button(
            "Run Comparison",
            type="primary",
            use_container_width=True,
        )

    if run_clicked:
        session = session_map[selected_session_id]
        try:
            artifact = _run_for_session(
                session=session,
                use_live_model=use_live_model,
                model=model_name,
                max_tokens=int(max_tokens),
                temperature=float(temperature),
            )
        except Exception as exc:
            st.error(f"Run failed: {exc}")
            return

        st.subheader("Scores")
        c1, c2, c3 = st.columns(3)
        c1.metric("Ground Truth", artifact["ground_truth_score"])
        c2.metric(
            "Baseline",
            artifact["baseline_score"],
            delta=artifact["baseline_score"] - artifact["ground_truth_score"],
        )
        c3.metric(
            "Arbitrated",
            artifact["arbitrated_score"],
            delta=artifact["arbitrated_score"] - artifact["ground_truth_score"],
        )

        st.caption(
            "Mode: "
            f"`{artifact['model_mode']['mode']}` | "
            f"Baseline match: `{artifact['baseline_match']}` | "
            f"Arbitrated match: `{artifact['arbitrated_match']}`"
        )

        summary = artifact["arbitration_trace_summary"]
        s1, s2, s3 = st.columns(3)
        s1.metric("ReasonTree Nodes", int(summary["reason_tree_node_count"]))
        s2.metric("Hydra Passes", int(summary["hydra_pass_count"]))
        s3.metric("Trace Entries", int(artifact["trace_entry_count"]))

        tab1, tab2, tab3, tab4 = st.tabs(
            ["Session Turns", "Trace Summary", "Trace Explorer", "Raw JSON"]
        )

        with tab1:
            st.dataframe(artifact["session_turns"], use_container_width=True)

        with tab2:
            st.write(
                {
                    "node_sequence": summary["reason_tree_node_sequence"],
                    "final_node_output": summary["final_node_output"],
                }
            )

        with tab3:
            pass_entries = [
                e
                for e in artifact["arbitration_trace_entries"]
                if e["component"] == "hydradecide" and e["step"] == "hydra_pass"
            ]
            st.caption(f"Hydra pass entries: {len(pass_entries)}")
            for idx, entry in enumerate(pass_entries, start=1):
                node_id = entry["input_payload"].get("node_id", "")
                pass_index = entry["input_payload"].get("pass_index", "")
                with st.expander(f"{idx}. {node_id} / pass {pass_index}"):
                    st.code(
                        str(entry["input_payload"].get("prompt", "")),
                        language="text",
                    )
                    st.code(
                        str(entry["output_payload"].get("pass_output", "")),
                        language="json",
                    )

        with tab4:
            st.json(artifact, expanded=False)
    else:
        st.info("Choose settings in the sidebar, then click `Run Comparison`.")


if __name__ == "__main__":
    main()
