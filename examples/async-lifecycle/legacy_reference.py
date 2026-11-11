"""Recheck the 618 retained scalar/all-starts-first outcomes using both models."""

import reference_history
import reference_state


def expected(case, history=False):
    if "async_trace" in case:
        trace = case["async_trace"]
        events = [{"start": v} for v in trace["values"]]
        events += [{"complete": i} for i in trace["complete"]]
        model = reference_history if history else reference_state
        return model.expected({"events": events})
    value = case["value"]
    valid = (
        reference_history.valid(value)
        if history
        else isinstance(value, str) and bool(value.strip())
    )
    return {
        "component": {"type": "input", "name": "display_name", "label": "Continue"},
        "payload": {"display_name": value},
        "response": {"ok": valid, "field": "display_name", "error": None if valid else "required"},
    }
