# Explicit Arbitration

Minimal arbitration demo for negotiation scoring with:
- deterministic ground-truth scoring
- baseline single-pass scoring
- ReasonTree + HydraDecide arbitrated scoring
- trace emission for transparency
- mandatory live LLM calls for product-facing runs

## Configure Model Access

DeepSeek is supported through its OpenAI-compatible endpoint:

```bash
export DEEPSEEK_API_KEY="..."
export MODEL_NAME="deepseek-v4-flash"
```

You can also use any OpenAI-compatible provider:

```bash
export ARBITRATION_API_KEY="..."
export ARBITRATION_BASE_URL="https://api.deepseek.com"
export MODEL_NAME="deepseek-v4-flash"
```

`OPENAI_API_KEY` and `OPENAI_BASE_URL` are also accepted for OpenAI-compatible
providers.

## Run

```bash
uv run python -m explicit_arbitration.arbitrated_runner \
  --model deepseek-v4-flash \
  --max-tokens 300 \
  --temperature 0 \
  > run_output.json
```

## Notes

- Runtime mode requires a configured API key and calls an OpenAI-compatible Chat Completions endpoint.
- Unit tests use injected fake model calls for deterministic verification.
- Output artifact includes `model_mode` so you can verify the endpoint and model used.

## Streamlit Frontend

Launch the lightweight UI without changing project dependencies:

```bash
uv run --with streamlit streamlit run app.py
```

In the UI, choose:
- sample session
- model/max-tokens/temperature

Then click `Run Comparison` to inspect scores and full arbitration traces.
The UI also shows a live event stream (node/pass lifecycle + progress) while arbitration runs.
