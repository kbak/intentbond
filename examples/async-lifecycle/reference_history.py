"""Prefix-history specification using dominance of starts and Unicode categories."""

import unicodedata

from contract import validate


def valid(value):
    return isinstance(value, str) and any(
        not (unicodedata.category(c) == "Zs" or unicodedata.bidirectional(c) in {"WS", "B", "S"})
        for c in value
    )


def expected(case):
    events = case["events"]
    validate(events)
    values = [e["start"] for e in events if "start" in e]
    states = []
    for end, event in enumerate(events, 1):
        prefix = events[:end]
        starts = [i for i, e in enumerate(prefix) if "start" in e]
        completions = [e["complete"] for e in prefix if "complete" in e]
        accepted = [
            e["complete"]
            for pos, e in enumerate(prefix)
            if "complete" in e
            and e["complete"] == sum("start" in earlier for earlier in prefix[:pos]) - 1
        ]
        error = None if not accepted or valid(values[accepted[-1]]) else "required"
        states.append(
            {
                "event": f"start:{len(starts) - 1}"
                if "start" in event
                else f"complete:{event['complete']}",
                "error": error,
                "pending": len(starts) - 1 not in completions,
            }
        )
    return {
        "component": {"type": "input", "name": "display_name", "label": "Continue"},
        "requests": [{"display_name": v} for v in values],
        "states": states,
    }
