# [impl->req~reservation-capacity~1]
# [impl->req~reservation-idempotency~1]
# [impl->req~reservation-atomic~1]
# [impl->req~reservation-cancel~1]
# [impl->req~reservation-batch~1]
from api_contract import error
from service import Service
from store import Store


def execute(case):
    store = Store(case["capacity"])
    service = Service(store)
    observations = []
    for op in case["operations"]:
        if op["op"] == "reserve":
            result = service.reserve(op["key"], op["qty"])
        elif op["op"] == "cancel":
            result = service.cancel(op["key"])
        elif op["op"] == "batch":
            result = service.batch(op["items"])
        else:
            result = error(400, "operation")
        observations.append({"result": result, "state": store.state()})
    return observations
