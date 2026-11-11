# [impl->req~form-wire~1]
# [impl->req~form-nonblank~1]
# [impl->req~form-label~2]
# [impl->req~form-async~1]
from schema import payload
from server import validate


class Form:
    def __init__(self):
        self.serial = 0
        self.error = None
        self.pending = False

    def submit(self, value):
        return validate(payload(value))

    async def validate(self, value, request):
        self.serial += 1
        serial = self.serial
        self.pending = True
        response = await request(payload(value))
        if serial == self.serial:
            self.error = response["error"]
            self.pending = False
