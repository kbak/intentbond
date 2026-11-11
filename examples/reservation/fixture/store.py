# [impl->req~reservation-capacity~1]
# [impl->req~reservation-idempotency~1]
# [impl->req~reservation-atomic~1]
# [impl->req~reservation-cancel~1]
# [impl->req~reservation-batch~1]
class Store:
    def __init__(self, capacity):
        self.capacity = capacity
        self.active = {}
        self.seen = {}

    def used(self):
        return sum(self.active.values())

    def state(self):
        return {"active": dict(self.active), "seen": dict(self.seen)}

    def restore(self, state):
        self.active, self.seen = dict(state["active"]), dict(state["seen"])
