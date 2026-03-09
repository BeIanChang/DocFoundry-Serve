# TODO

## Done (priority)

- [x] JWT handling compatible with DocFoundry tokens (HS256, `sub/email/name`, `Authorization: Bearer ...`)
- [x] Readiness endpoint checks vLLM upstream and model availability
- [x] Typed upstream error handling with retries and retry budget
- [x] Admission control: max in-flight, queue cap, queue wait timeout, stage-aware load shedding
- [x] Async batched metrics writer (JSONL/CSV) to reduce per-request file write contention

## Next candidates

- [ ] Prometheus metrics endpoint and OpenTelemetry traces
- [ ] Stage-aware timeout budgets and dynamic policy downgrades under load
- [ ] Request id propagation through benchmark scripts and downstream traces
- [ ] Redis-backed queue + worker pool path for burst smoothing
- [ ] Canary policy experiments and online A/B routing
