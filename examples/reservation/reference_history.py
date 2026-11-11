"""D2 event-log model reused by D4; independent of the transition checker."""


def reservation_model(case, version):
    # An event log is the authority; unsuccessful transactions append no events.
    history = []
    observations = []

    def state(events):
        active, seen = {}, {}
        for event in events:
            if event[0] == "reserved":
                active[event[1]] = event[2]
                seen[event[1]] = event[2]
            elif event[0] == "cancelled":
                active.pop(event[1], None)
        return {"active": active, "seen": seen}

    def reserve(events, key, qty):
        view = state(events)
        if not isinstance(key, str) or not key or type(qty) is not int or qty < 1:
            return {"status": 400, "error": "invalid"}, []
        if key in view["seen"]:
            if view["seen"][key] != qty:
                return {"status": 409, "error": "conflict"}, []
            return {"status": 200, "reservation": key, "quantity": qty}, []
        remaining = case["capacity"]
        for quantity in view["active"].values():
            remaining -= quantity
        if qty > remaining:
            return {"status": 409, "error": "capacity"}, []
        return {"status": 200, "reservation": key, "quantity": qty}, [("reserved", key, qty)]

    for op in case["operations"]:
        events = []
        if op["op"] == "reserve":
            result, events = reserve(history, op["key"], op["qty"])
        elif op["op"] == "cancel" and version >= 1:
            if op["key"] not in state(history)["seen"]:
                result = {"status": 404, "error": "unknown"}
            else:
                result = {"status": 200, "cancelled": op["key"]}
                events = [("cancelled", op["key"])]
        elif op["op"] == "batch" and version >= 2:
            responses = []
            for item in op["items"]:
                response, extra = reserve(history + events, item["key"], item["qty"])
                if response["status"] != 200:
                    events = []
                    result = {"status": response["status"], "error": "batch_failed"}
                    break
                responses.append(response)
                events += extra
            else:
                result = {"status": 200, "reservations": responses}
        else:
            result = {"status": 400, "error": "operation"}
        history += events
        observations.append({"result": result, "state": state(history)})
    return observations
