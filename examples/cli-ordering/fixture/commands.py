# [impl->req~export-text~1]
# [impl->req~export-order~1]
# [impl->req~export-errors~1]
# [impl->req~export-json~1]
# [impl->req~export-stream~1]
import formatters
from compatibility import option_error
from parser import parse


def run(argv, rows):
    try:
        mode = parse(argv)
    except ValueError:
        return option_error()
    rows = formatters.ordered(rows)
    renderer = {"text": formatters.text, "json": formatters.array, "stream": formatters.stream}[
        mode
    ]
    return {"code": 0, "out": renderer(rows), "err": ""}
