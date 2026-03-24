# Multi-Tenant Experiment Plan

## Goal

Benchmark DocFoundry and DocFoundry-Serve under a realistic multi-tenant workload and report throughput, latency, and isolation metrics.

## Phases

### 1. Serve-only smoke

- Use prompt packs only.
- Validate baseline vs stage-aware routing.
- Report requests/sec, tokens/sec, and p95 latency.

### 2. End-to-end small

- Generate multiple tenant corpora from the one-user templates.
- Ingest them into DocFoundry.
- Run scoped `/agent/query` workloads per tenant.
- Verify no cross-tenant citation leakage.

### 3. End-to-end medium

- Increase tenant count and concurrency.
- Compare classic and LangGraph loops if available.
- Report saturation behavior and tail latency.

## Initial Resume-Safe Claim

Use the first successful end-to-end run with clearly documented hardware, tenant count, total documents, concurrency, throughput, and p95 latency.

Example wording:

- Benchmarked a multi-tenant document reasoning pipeline across N tenants and M documents.
- Measured end-to-end throughput and p95 latency under mixed workloads.
- Verified scoped retrieval and citation isolation across tenants.

## Required Artifacts

- tenant corpus manifest
- ingestion log
- benchmark result JSONL
- latency summary CSV
- leakage/citation validation summary
