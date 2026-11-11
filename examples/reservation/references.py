"""Requirement-derived reservation traces and independent transition invariants."""

import copy
import itertools
import json
import re

ATOMIC = "req~reservation-atomic~1"
IDEMPOTENCY = "req~reservation-idempotency~1"
CAPACITY = "req~reservation-capacity~1"
CANCEL = "req~reservation-cancel~1"
BATCH = "req~reservation-batch~1"
ALL = {ATOMIC, IDEMPOTENCY, CAPACITY, CANCEL, BATCH}


def clauses(source, digest):
    text = (source / "requirements.md").read_text()
    result = []
    for name, section in re.findall(r"### ([^\n]+)\n(.*?)(?=### |\Z)", text, re.S):
        ref = re.search(r"`(req~[^`]+)`", section).group(1)
        offset = text.index("### " + name)
        row = {
            "requirement": ref,
            "text": section.strip(),
            "source": {
                "path": "requirements.md",
                "sha256": digest,
                "line": text[:offset].count("\n") + 1,
            },
        }
        if ref == ATOMIC:
            row["temporary_clauses"] = [
                {
                    "id": "rollback.active",
                    "meaning": "unsuccessful operations preserve all active reservations",
                },
                {
                    "id": "rollback.history",
                    "meaning": "unsuccessful operations preserve all successful-key history",
                },
                {
                    "id": "rollback.batch",
                    "meaning": "a whole failed batch has no partial effects",
                },
            ]
        if ref == IDEMPOTENCY:
            row["temporary_clauses"] = [
                {
                    "id": "replay.same",
                    "meaning": "same key/quantity returns the original success without state change",
                },
                {
                    "id": "replay.cancelled",
                    "meaning": "cancellation retains history and replay does not reactivate",
                },
                {
                    "id": "replay.conflict",
                    "meaning": "different quantity conflicts without state change",
                },
            ]
        result.append(row)
    if {r["requirement"] for r in result} != ALL:
        raise ValueError("unsupported maintained requirements")
    return result


def reserve(key, qty):
    return {"op": "reserve", "key": key, "qty": qty}


def cancel(key):
    return {"op": "cancel", "key": key}


def batch(*pairs):
    return {"op": "batch", "items": [{"key": k, "qty": q} for k, q in pairs]}


def generate(phase):
    cases = []

    def add(capacity, operations, targets, kind="positive"):
        cases.append(
            {
                "id": f"{phase}-{len(cases):03}",
                "targets": targets,
                "kind": kind,
                "input": {"capacity": capacity, "operations": operations},
            }
        )

    if phase == "initial":
        add(0, [batch()], [BATCH, ATOMIC])
        add(3, [batch(("a", 1), ("b", 2))], [BATCH, CAPACITY])
        add(2, [batch(("a", 1), ("a", 1)), reserve("a", 1)], [BATCH, IDEMPOTENCY])
        add(
            3,
            [
                reserve("a", 1),
                reserve("a", 1),
                reserve("a", 2),
                cancel("a"),
                reserve("a", 1),
                cancel("a"),
                reserve("b", 3),
            ],
            [IDEMPOTENCY, CANCEL, CAPACITY, ATOMIC],
        )
        # Fail after one successful member, then retry the leaked key at a different quantity.
        for bad in [("b", 3), ("b", 0), ("a", 2), ("", 1), ("b", True)]:
            add(
                2,
                [batch(("a", 1), bad), reserve("a", 2), cancel("a"), reserve("a", 2)],
                [ATOMIC, BATCH, IDEMPOTENCY],
                "negative_input",
            )
        add(
            3,
            [
                reserve("old", 1),
                batch(("new", 1), ("more", 3)),
                reserve("old", 1),
                reserve("new", 2),
            ],
            [ATOMIC, IDEMPOTENCY, CAPACITY],
        )
        add(
            3,
            [
                reserve("old", 1),
                cancel("old"),
                batch(("new", 1), ("old", 2)),
                reserve("old", 1),
                reserve("old", 2),
                reserve("new", 3),
            ],
            [ATOMIC, IDEMPOTENCY, CANCEL],
        )
        # These passing preservation cases are also retained in the regression suite.
        add(
            3,
            [
                reserve("old", 1),
                cancel("old"),
                batch(("old", 1), ("new", 3)),
                reserve("old", 1),
                reserve("old", 2),
                cancel("old"),
                cancel("new"),
                reserve("new", 3),
            ],
            [IDEMPOTENCY, CANCEL, BATCH, CAPACITY],
        )
        add(
            2,
            [
                batch(("a", 1), ("b", 1)),
                batch(("a", 1), ("b", 1)),
                cancel("a"),
                batch(("a", 1)),
                reserve("a", 2),
            ],
            [IDEMPOTENCY, BATCH, CANCEL],
        )
        add(
            2,
            [batch(("a", 0), ("b", 1)), reserve("b", 2)],
            [ATOMIC, CAPACITY],
            "negative_input",
        )
        add(
            1,
            [
                cancel("missing"),
                cancel("missing"),
                reserve("a", 1),
                cancel("a"),
                cancel("a"),
            ],
            [CANCEL, ATOMIC],
        )
        add(
            1,
            [
                reserve("a", 0),
                reserve("a", -1),
                reserve("a", True),
                reserve("a", 1.5),
                reserve("a", 1),
                reserve("b", 1),
            ],
            [CAPACITY, ATOMIC],
            "negative_input",
        )
        add(1, [{"op": "unknown"}, batch()], [ATOMIC, BATCH], "negative_input")
    elif phase == "adversarial":
        atoms = [("a", 1), ("a", 2), ("b", 1), ("b", 0)]
        prefixes = [[], [reserve("a", 1)], [reserve("a", 1), cancel("a")]]
        suffix = [
            reserve("a", 1),
            reserve("a", 2),
            cancel("a"),
            cancel("a"),
            reserve("a", 1),
            reserve("b", 1),
        ]
        for capacity in (2, 3):
            for prefix in prefixes:
                for length in range(4):
                    for pairs in itertools.product(atoms, repeat=length):
                        add(
                            capacity,
                            prefix + [batch(*pairs)] + suffix,
                            [ATOMIC, IDEMPOTENCY, BATCH, CANCEL, CAPACITY],
                        )
    else:
        raise ValueError("unknown phase")
    return cases


def decode(case, outcome):
    # Strict JSON equality distinguishes integer quantities from booleans/floats.
    return json.dumps(outcome, sort_keys=True, separators=(",", ":"), allow_nan=False)


def transition_check(case, observed):
    """Pure state transitions; no candidate imports and no event-log reference calls."""

    def error(status, reason):
        return {"status": status, "error": reason}

    def one(state, key, qty):
        active, history = state
        if not isinstance(key, str) or not key or type(qty) is not int or qty <= 0:
            return error(400, "invalid"), state
        if key in history:
            if history[key] != qty:
                return error(409, "conflict"), state
            return {"status": 200, "reservation": key, "quantity": qty}, state
        if sum(active.values()) + qty > case["capacity"]:
            return error(409, "capacity"), state
        return (
            {"status": 200, "reservation": key, "quantity": qty},
            ({**active, key: qty}, {**history, key: qty}),
        )

    if not isinstance(observed, list) or len(observed) != len(case["operations"]):
        return False
    state = ({}, {})
    for operation, actual in zip(case["operations"], observed):
        before = state
        if operation["op"] == "reserve":
            result, state = one(state, operation["key"], operation["qty"])
        elif operation["op"] == "cancel":
            key = operation["key"]
            if key not in state[1]:
                result = error(404, "unknown")
            else:
                result = {"status": 200, "cancelled": key}
                state = ({k: v for k, v in state[0].items() if k != key}, state[1])
        elif operation["op"] == "batch":
            transaction, responses = state, []
            for request in operation["items"]:
                result, transaction = one(transaction, request["key"], request["qty"])
                if result["status"] != 200:
                    result = error(result["status"], "batch_failed")
                    break
                responses.append(result)
            else:
                state = transaction
                result = {"status": 200, "reservations": responses}
        else:
            result = error(400, "operation")
        # Check rollback independently of the expected response comparison.
        if result["status"] != 200 and state != before:
            raise AssertionError("reference transition violated atomicity")
        expected = {"result": result, "state": {"active": state[0], "seen": state[1]}}
        if decode(case, actual) != decode(case, expected):
            return False
    return True


def contract_accepts(case, observed):
    try:
        return transition_check(case, observed)
    except (TypeError, ValueError, KeyError):
        return False


def negative_outputs(cases):
    # Hand-specified invalid traces probe errors without querying either candidate or oracle.
    failed = {"capacity": 2, "operations": [batch(("a", 1), ("b", 3))]}
    empty = {"active": {}, "seen": {}}
    rows = []
    for state in (
        {"active": {"a": 1}, "seen": {}},
        {"active": {}, "seen": {"a": 1}},
        {"active": {"a": 1}, "seen": {"a": 1}},
    ):
        rows.append(
            {
                "targets": [ATOMIC],
                "input": failed,
                "output": [{"result": {"status": 409, "error": "batch_failed"}, "state": state}],
            }
        )
    rows.append(
        {
            "targets": [BATCH],
            "input": {"capacity": 0, "operations": [batch()]},
            "output": [{"result": {"status": 409, "error": "batch_failed"}, "state": empty}],
        }
    )
    legal = {
        "capacity": 1,
        "operations": [reserve("a", 1), cancel("a"), reserve("a", 1)],
    }
    trace = [
        {
            "result": {"status": 200, "reservation": "a", "quantity": 1},
            "state": {"active": {"a": 1}, "seen": {"a": 1}},
        },
        {
            "result": {"status": 200, "cancelled": "a"},
            "state": {"active": {}, "seen": {"a": 1}},
        },
        {
            "result": {"status": 200, "reservation": "a", "quantity": 1},
            "state": {"active": {"a": 1}, "seen": {"a": 1}},
        },
    ]
    rows.append({"targets": [IDEMPOTENCY], "input": legal, "output": trace})
    lost = copy.deepcopy(trace)
    lost[1]["state"]["seen"] = {}
    rows.append({"targets": [IDEMPOTENCY, CANCEL], "input": legal, "output": lost})
    return rows
