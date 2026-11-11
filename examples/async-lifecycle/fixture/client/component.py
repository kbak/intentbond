from schema import WIRE_FIELD


def render(label):
    return {"type": "input", "name": WIRE_FIELD, "label": label}
