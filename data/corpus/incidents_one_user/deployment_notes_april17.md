# Deployment Notes - April 17

The billing worker deployment at 08:58 UTC introduced a new retry policy for failed write operations.

The retry change increased the per-job retry cap from 2 attempts to 6 attempts and reduced the wait time between retries.

No schema migrations were included in this deployment.

Rollback completed at 09:46 UTC after incident review by the on-call engineer.
