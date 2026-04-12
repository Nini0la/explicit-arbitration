# Explicit Arbitration

Minimal arbitration demo for negotiation scoring with:
- deterministic ground-truth scoring
- baseline single-pass scoring
- ReasonTree + HydraDecide arbitrated scoring
- trace emission for transparency

## Run (Stub Mode, Deterministic)

```bash
uv run python -m explicit_arbitration.arbitrated_runner > run_output.json
```

## Run (Live Model Mode)

Set credentials/config:

```bash
export OPENAI_API_KEY="..."
# optional:
export OPENAI_BASE_URL="https://api.openai.com/v1"
export MODEL_NAME="gpt-4.1-mini"
```

Run:

```bash
uv run python -m explicit_arbitration.arbitrated_runner --use-live-model > run_output.json
```

Optional runtime overrides:

```bash
uv run python -m explicit_arbitration.arbitrated_runner \
  --use-live-model \
  --model gpt-4.1-mini \
  --max-tokens 300 \
  --temperature 0
```

## Notes

- Default mode is stubbed for deterministic tests.
- Live mode uses an OpenAI-compatible Chat Completions endpoint.
- Output artifact includes `model_mode` so you can verify whether the run used stub or live calls.

## Streamlit Frontend

Launch the lightweight UI without changing project dependencies:

```bash
uv run --with streamlit streamlit run app.py
```

In the UI, choose:
- sample session
- stub vs live model mode
- model/max-tokens/temperature (live mode settings)

Then click `Run Comparison` to inspect scores and full arbitration traces.
