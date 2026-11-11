# [impl->req~form-wire~1]
# [impl->req~form-nonblank~1]
# [impl->req~form-label~2]
# [impl->req~form-async~1]
from schema import WIRE_FIELD


def validate(data):
    value = data.get(WIRE_FIELD)
    ok = isinstance(value, str) and bool(value.strip())
    return {"ok": ok, "field": WIRE_FIELD, "error": None if ok else "required"}
