# [impl->req~export-text~1]
# [impl->req~export-order~1]
# [impl->req~export-errors~1]
# [impl->req~export-json~1]
# [impl->req~export-stream~1]
import json


def ordered(rows):
    return sorted(rows, key=lambda row: (row["name"], row["qty"]))


def text(rows):
    return "".join(f"{row['name']}\t{row['qty']}\n" for row in rows)


def array(rows):
    return json.dumps(list(rows), separators=(",", ":")) + "\n"


def stream(rows):
    return "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows)
