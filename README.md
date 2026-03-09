# DocFoundry-Serve

Stage-aware inference serving layer for agentic document reasoning.

## Motivation

Agentic workflows do not have uniform generation needs across steps. Planning should be fast and concise, synthesis needs larger output windows, and refinement should be stable and deterministic. `DocFoundry-Serve` provides a policy-aware gateway in front of vLLM so each stage gets a tuned generation profile while preserving benchmark reproducibility.

## Architecture

`FastAPI Gateway -> Auth -> Admission Control -> Policy Router -> vLLM(OpenAI API) -> Batched Metrics Sink`

- `POST /generate` accepts `stage`, `prompt`, and optional `metadata`.
- JWT auth is compatible with DocFoundry tokens (`HS256`, `sub/email/name`, Bearer header).
- Admission control enforces in-flight limits, queue caps, queue timeout, and stage-aware load shedding.
- Policy router selects config by stage (`planning`, `synthesis`, `refinement`) or baseline mode.
- vLLM client streams responses when possible to capture TTFT, with typed errors and retry budget.
- Per-request metrics are batched and flushed to JSONL or CSV asynchronously.

Core modules:

- `app/api.py`: endpoint and request handling
- `app/router/policy_router.py`: stage-to-policy mapping
- `app/clients/vllm_client.py`: OpenAI-compatible vLLM wrapper
- `app/services/generate_service.py`: orchestration logic
- `app/metrics/*`: metrics collection and persistence
- `scripts/benchmark_mixed.py`: mixed-stage workload benchmark
- `scripts/analyze_results.py`: baseline vs stage-aware analysis

## Request Contract

`POST /generate`

```json
{
  "stage": "planning",
  "prompt": "Plan retrieval strategy for this question...",
  "metadata": {
    "trace_id": "optional"
  }
}
```

Example response fields:

- `text`: model output
- `policy`: selected policy name, mode, and generation config
- `metrics.total_latency_ms`
- `metrics.ttft_ms` (null if not available)
- `metrics.output_tokens`
- `metrics.policy_used`

Headers:

- `Authorization: Bearer <jwt>` (required when `AUTH_REQUIRED=true`)
- `X-Router-Mode: baseline|stage_aware` (optional override)

Operational endpoints:

- `GET /health`: liveness
- `GET /ready`: readiness (checks vLLM and model availability + admission snapshot)

## Stage Policies

Defined in `config/policies.yaml`:

- `planning`: low latency (`max_tokens` small, low `temperature`)
- `synthesis`: longer output budget and medium creativity
- `refinement`: low temperature and medium output for stable formatting
- `baseline`: single shared generation config for all stages

## Setup

### 1) Python local run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Set env vars as needed:

- `VLLM_BASE_URL` (default: `http://localhost:8001/v1`)
- `VLLM_MODEL`
- `ROUTER_MODE` (`baseline` or `stage_aware`)
- `METRICS_PATH` and `METRICS_FORMAT` (`jsonl` or `csv`)
- `AUTH_REQUIRED` (`true`/`false`, default `false`)
- `JWT_SECRET` and `JWT_ALGORITHM` (DocFoundry-compatible defaults)
- `MAX_IN_FLIGHT`, `MAX_QUEUE`, `QUEUE_WAIT_TIMEOUT_SECONDS`
- `STAGE_QUEUE_LIMITS` (example: `planning:200,synthesis:120,refinement:120`)
- `STAGE_IN_FLIGHT_LIMITS` (example: `planning:48,synthesis:24,refinement:24`)
- `VLLM_MAX_RETRIES`, `VLLM_RETRY_BACKOFF_MS`
- `METRICS_BATCH_SIZE`, `METRICS_FLUSH_INTERVAL_SECONDS`

### 2) Docker Compose run (gateway + vLLM)

```bash
docker compose up --build
```

Endpoints:

- Gateway: `http://localhost:8000`
- vLLM OpenAI endpoint: `http://localhost:8001/v1`

## Benchmark Reproducibility

Run mixed workload in both modes:

```bash
python scripts/benchmark_mixed.py --config config/benchmark.yaml --modes baseline stage_aware --output-dir data/benchmarks
```

If auth is enabled on gateway:

```bash
python scripts/benchmark_mixed.py --auth-token "$DOCFOUNDRY_SERVE_TOKEN"
```

This writes:

- `data/benchmarks/results_baseline.jsonl`
- `data/benchmarks/results_stage_aware.jsonl`

Then analyze:

```bash
python scripts/analyze_results.py \
  --baseline data/benchmarks/results_baseline.jsonl \
  --stage-aware data/benchmarks/results_stage_aware.jsonl \
  --output data/benchmarks/analysis_summary.csv
```

## Analysis Outputs

The analyzer reports:

- average latency
- p95 latency
- tokens/sec
- per-stage breakdown (`planning`, `synthesis`, `refinement`)

and saves summary CSV to `data/benchmarks/analysis_summary.csv`.

## Expected Output Pattern

Typical behavior when policies are well-tuned:

- `planning` latency improves in stage-aware mode
- `synthesis` preserves or improves tokens/sec due to larger token budget
- `refinement` shows lower variance from lower temperature settings

Results depend on model, GPU, prompt mix, and system load, so compare runs with fixed seed and identical hardware.
