# [impl->req~reservation-capacity~1]
# [impl->req~reservation-idempotency~1]
# [impl->req~reservation-atomic~1]
# [impl->req~reservation-cancel~1]
# [impl->req~reservation-batch~1]
import copy

from api_contract import error


class Service:
    def __init__(self, store):
        self.store = store

    def reserve(self, key, qty):
        if not isinstance(key, str) or not key or type(qty) is not int or qty <= 0:
            return error(400, "invalid")
        if key in self.store.seen:
            if self.store.seen[key] != qty:
                return error(409, "conflict")
            return {"status": 200, "reservation": key, "quantity": qty}
        if self.store.used() + qty > self.store.capacity:
            return error(409, "capacity")
        self.store.active[key] = qty
        self.store.seen[key] = qty
        return {"status": 200, "reservation": key, "quantity": qty}

    def cancel(self, key):
        if key not in self.store.seen:
            return error(404, "unknown")
        self.store.active.pop(key, None)
        return {"status": 200, "cancelled": key}

    def batch(self, items):
        staged = copy.copy(self.store)
        results = []
        for item in items:
            result = Service(staged).reserve(item["key"], item["qty"])
            if result["status"] != 200:
                return error(result["status"], "batch_failed")
            results.append(result)
        self.store.restore(staged.state())
        return {"status": 200, "reservations": results}
