# Accepted requirements

### reservation-capacity
`req~reservation-capacity~1`

Positive integer quantities can be reserved while their total active quantity is at most capacity. Invalid quantities return 400 and insufficient capacity returns 409.

Needs: impl, utest

### reservation-idempotency
`req~reservation-idempotency~1`

Repeating a successful reservation key with the same quantity returns the original successful response without changing any state, including after cancellation; different quantities conflict.

Needs: impl, utest

### reservation-atomic
`req~reservation-atomic~1`

Any unsuccessful operation leaves all active reservations and the entire idempotency history unchanged. This also applies to a future batch operation as a whole.

Needs: impl, utest

### reservation-cancel
`req~reservation-cancel~1`

Cancel releases capacity once and succeeds idempotently for any previously successful key. Unknown keys return 404. Cancellation never erases reservation idempotency history.

Needs: impl, utest

### reservation-batch
`req~reservation-batch~1`

Batch applies reservation requests in order atomically. It returns status 200 and all reservation responses on success; on any failure it returns that status and error batch_failed and leaves the entire store unchanged. Empty batches succeed.

Needs: impl, utest

