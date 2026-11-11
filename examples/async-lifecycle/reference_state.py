"""Latest-started ordinal state machine, independent of candidate request IDs."""

from contract import validate


def expected(case):
    events = case["events"]
    validate(events)
    values = []
    states = []
    error = None
    pending = False
    for event in events:
        if "start" in event:
            values.append(event["start"])
            pending = True
            name = f"start:{len(values) - 1}"
        else:
            index = event["complete"]
            name = f"complete:{index}"
            if index == len(values) - 1:
                value = values[index]
                error = None if isinstance(value, str) and bool(value.strip()) else "required"
                pending = False
        states.append({"event": name, "error": error, "pending": pending})
    return {
        "component": {"type": "input", "name": "display_name", "label": "Continue"},
        "requests": [{"display_name": value} for value in values],
        "states": states,
    }
