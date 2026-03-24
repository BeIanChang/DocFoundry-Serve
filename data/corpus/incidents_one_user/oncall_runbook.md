# On-Call Runbook

## Elevated API Latency

When p95 latency exceeds 2 seconds for more than 10 minutes, the on-call engineer should first check database saturation, recent deploys, and queue backlog.

If a recent deployment correlates with the start of the incident, the preferred mitigation is rollback before broader config tuning.

Database connection pool exhaustion should be confirmed through connection metrics, worker concurrency counts, and error logs showing timeout or pool-acquire failures.

Escalate to the database owner if connection pressure continues for more than 15 minutes after rollback.
