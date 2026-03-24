# Incident Postmortem - API Latency Spike

## Summary

On April 17, the customer API experienced elevated p95 latency from 09:12 to 10:03 UTC. The issue primarily affected write-heavy endpoints in the billing and order-update paths.

## Root Cause

The primary cause was connection pool exhaustion on the metadata database after a deployment changed retry behavior in the billing worker. The new worker logic retried failed writes too aggressively and increased concurrent DB usage.

## Impact

Approximately 18 percent of write requests exceeded the 2-second internal SLO during the event window. Read-only traffic was degraded but remained partially available.

## Remediation

The on-call engineer rolled back the worker deployment at 09:46 UTC. Latency began improving within 5 minutes, and normal service resumed by 10:03 UTC.
