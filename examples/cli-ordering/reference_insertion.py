"""D2 stable-insertion reference, independent of the candidate sort."""

import json


def export_model(case, version):
    args = case["args"]
    allowed = [[], ["--json"]] + ([["--stream"]] if version >= 2 else [])
    if version == 0:
        allowed = [[]]
    if args not in allowed:
        return {"code": 2, "out": "", "err": "invalid options\n"}
    # Stable insertion by original position, independently of the candidate's sort.
    rows = []
    for original in case["rows"]:
        index = next(
            (i for i, row in enumerate(rows) if row["name"] > original["name"]),
            len(rows),
        )
        rows.insert(index, dict(original))
    if args == ["--json"]:
        output = json.dumps(rows) + "\n"
    elif args == ["--stream"]:
        output = "".join(json.dumps(row) + "\n" for row in rows)
    else:
        output = "".join(str(row["name"]) + "\t" + str(row["qty"]) + "\n" for row in rows)
    return {"code": 0, "out": output, "err": ""}
