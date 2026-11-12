# [impl->req~export-text~1]
# [impl->req~export-order~1]
# [impl->req~export-errors~1]
# [impl->req~export-json~1]
# [impl->req~export-stream~1]
from commands import run


def evaluate(case):
    return run(case["args"], case["rows"])
