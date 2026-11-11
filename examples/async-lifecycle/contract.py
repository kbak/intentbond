"""Input shape for the versioned D11 normal-response lifecycle profile."""

ASYNC = "req~form-async~1"
REQUIREMENTS = ["req~form-async~1", "req~form-label~2", "req~form-nonblank~1", "req~form-wire~1"]
CHECK = "utest~d11-async-lifecycle~1"


def validate(events):
    if not isinstance(events, list) or not events:
        raise ValueError("nonempty event sequence required")
    started = 0
    pending = set()
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("invalid event")
        if set(event) == {"start"}:
            pending.add(started)
            started += 1
        elif (
            set(event) == {"complete"}
            and type(event["complete"]) is int
            and event["complete"] in pending
        ):
            pending.remove(event["complete"])
        else:
            raise ValueError("completion must select a pending request exactly once")
    if not started or pending:
        raise ValueError("every request must complete")
    return started
