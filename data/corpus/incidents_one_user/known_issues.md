# Known Issues

## Billing Worker

The billing worker can increase database pressure when retries are not rate-limited.

Historical incidents show that aggressive retries can amplify pool contention and create elevated write latency even when database CPU remains under control.

For this service, p95 latency above 2 seconds for sustained write traffic is treated as an operational incident requiring investigation.
