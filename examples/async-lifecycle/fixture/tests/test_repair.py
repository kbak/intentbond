import json
import unittest
from pathlib import Path


def decode(case, outcome):
    return json.dumps(outcome, sort_keys=True, separators=(",", ":"), allow_nan=False)


def probe(case):
    import asyncio

    from client.component import render
    from client.controller import Form
    from client.labels import LABEL
    from server import validate

    values, order = case["async_trace"]["values"], case["async_trace"]["complete"]
    if not values or sorted(order) != list(range(len(values))):
        raise ValueError("invalid completion schedule")

    async def sequence():
        form = Form()
        gates, tasks, requests, states = [], [], [None] * len(values), []
        for index, value in enumerate(values):
            gate = asyncio.get_running_loop().create_future()
            gates.append(gate)

            async def request(data, gate=gate, index=index):
                requests[index] = dict(data)
                await gate
                return validate(data)

            tasks.append(asyncio.create_task(form.validate(value, request)))
            await asyncio.sleep(0)
            states.append(
                {
                    "event": f"start:{index}",
                    "error": form.error,
                    "pending": form.pending,
                }
            )
        for index in order:
            gates[index].set_result(None)
            await tasks[index]
            states.append(
                {
                    "event": f"complete:{index}",
                    "error": form.error,
                    "pending": form.pending,
                }
            )
        await asyncio.gather(*tasks)
        return {"component": render(LABEL), "requests": requests, "states": states}

    return asyncio.run(sequence())


def evaluate_case(case):
    if "async_trace" in case:
        return probe(case)
    from entrypoint import evaluate

    return evaluate(case)


# [utest~d6-repair-regression~1->req~form-nonblank~1]
class Regression(unittest.TestCase):
    def test_cases(self):
        cases = json.loads(Path(__file__).with_name("repair_cases.json").read_text())
        for case in cases:
            with self.subTest(case=case["id"]):
                observed = decode(case["input"], evaluate_case(case["input"]))
                self.assertIn(observed, case["accepted"])
