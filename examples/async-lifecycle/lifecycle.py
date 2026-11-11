"""D11-v1: exhaustive <=3-request binary-value schedules plus exact D10 regressions."""

import copy
import inspect
import itertools
import json
from pathlib import Path

import contract
import observer
import reference_history
import reference_state

ROOT = Path(__file__).resolve().parent


def schedules(n):
    def extend(started, pending, path):
        if started == n and not pending:
            yield path
            return
        if started < n:
            yield from extend(started + 1, pending + (started,), path + [("start", started)])
        for index in pending:
            yield from extend(
                started, tuple(p for p in pending if p != index), path + [("complete", index)]
            )

    return list(extend(0, (), []))


def inputs():
    result = []
    for row in json.loads((ROOT / "regressions.json").read_text()):
        result.append(
            {"id": "d10-" + row["id"], "input": copy.deepcopy(row["input"]), "stage": "initial"}
        )
    for n in (1, 2, 3):
        for order, schedule in enumerate(schedules(n)):
            for bits, values in enumerate(itertools.product(("", "Ada"), repeat=n)):
                events = [
                    {"start": values[index]} if action == "start" else {"complete": index}
                    for action, index in schedule
                ]
                result.append(
                    {
                        "id": f"d11-n{n}-s{order:02}-v{bits:02}",
                        "input": {"events": events},
                        "stage": "initial" if n == 1 else "adversarial",
                    }
                )
    return result


def generate(stage, control="repair"):
    result = []
    for raw in inputs():
        if raw["stage"] != stage:
            continue
        label = {
            "status": "confirmed",
            "method": "incremental latest-started model agrees with prefix-history/Unicode-category model",
            "sources": [
                str(ROOT / "reference_state.py"),
                str(ROOT / "reference_history.py"),
                str(ROOT / "contract.py"),
            ],
        }
        accepted = []
        try:
            if control == "unavailable" and not result:
                raise LookupError("qualification: reference unavailable")
            first = reference_state.expected(raw["input"])
            second = reference_history.expected(raw["input"])
            if control == "conflict" and not result:
                second["states"][-1]["pending"] = not second["states"][-1]["pending"]
            if first != second:
                label["status"] = "conflict"
            else:
                accepted = [
                    json.dumps(first, sort_keys=True, separators=(",", ":"), allow_nan=False)
                ]
        except (ValueError, TypeError, KeyError, LookupError) as exc:
            label.update(status="unknown", reason=type(exc).__name__ + ": " + str(exc))
        result.append(
            {
                "id": raw["id"],
                "kind": "positive",
                "input": raw["input"],
                "requirements": contract.REQUIREMENTS,
                "accepted": accepted,
                "label": label,
            }
        )
    return result


def scaffold(config):
    text = "import asyncio\nimport json\nimport unittest\nfrom pathlib import Path\n\n"
    text += inspect.getsource(contract.validate) + "\n" + inspect.getsource(observer.observe) + "\n"
    text += f"# [{config['checks'][0]}->{contract.ASYNC}]\n"
    text += """class Lifecycle(unittest.TestCase):
    def test_events(self):
        rows=json.loads(Path(__file__).with_name('async_lifecycle_cases.json').read_text())
        for row in rows:
            with self.subTest(case=row['id']):
                actual=json.dumps(observe(row['input']),sort_keys=True,separators=(',',':'),allow_nan=False)
                self.assertIn(actual,row['accepted'])
"""
    return text


def proposal(source, control):
    path = "client/controller.py"
    text = (source / path).read_text()
    reset = "            # Reuse small counters once the latest response has completed.\n            self.serial = 0\n"
    if reset not in text:
        return None
    if control == "no-progress":
        changed = text.replace(
            "    async def validate(self, value, request):\n",
            "    async def validate(self, value, request):\n        # Qualification: keep the fault unchanged.\n",
        )
    elif control == "alternative":
        prefix = text[: text.index("    async def validate(self, value, request):")]
        changed = (
            prefix
            + """    async def validate(self, value, request):
        # Unique request identity cannot collide with an older pending request.
        serial = object()
        self.serial = serial
        self.pending = True
        response = await request(payload(value))
        if serial is self.serial:
            self.error = response['error']
            self.pending = False
"""
        )
    else:
        changed = text.replace(reset, "").replace(
            "    async def validate(self, value, request):\n",
            "    async def validate(self, value, request):\n        # Keep generations distinct while earlier requests may still finish.\n",
        )
    files = {path: changed}
    if control == "signature":
        files[path] = changed.replace("value, request):", "value, request=None):")
    if control == "protected":
        files["schema.py"] = (source / "schema.py").read_text() + "\nUNWANTED = True\n"
    if control == "old-test":
        files["tests/test_form_async.py"] = "# removed old assertion\n"
    if control == "requirement":
        files["requirements.md"] = ""
    return {
        "targets": [contract.ASYNC],
        "reason": "The retained interleaving shows a reused generation admits a stale response; preserve request identity until no older response can match it.",
        "files": files,
    }
